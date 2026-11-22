"""palmfx.offline.inpaint and the ``palmfx inpaint`` command."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from palmcore.errors import ConfigError
from palmfx.offline import cli
from palmfx.offline.commands.inpaint import parse_frames
from palmfx.offline.inpaint import (
    LamaInpainter,
    TeleaInpainter,
    Tile,
    check_weights,
    inpaint_tiled,
    load_models_lock,
    plan_tiles,
)
from palmfx.offline.session import MaskSet, new_session, write_image, write_mask


def gradient(h: int, w: int) -> NDArray[np.uint8]:
    y, x = np.mgrid[0:h, 0:w]
    img = np.stack(
        [x * 255 // max(w - 1, 1), y * 255 // max(h - 1, 1), (x + y) * 255 // (h + w)], -1
    )
    return img.astype(np.uint8)


def rect_mask(h: int, w: int, x0: int, y0: int, x1: int, y1: int) -> NDArray[np.uint8]:
    m = np.zeros((h, w), np.uint8)
    m[y0:y1, x0:x1] = 255
    return m


class Recorder:
    name = "rec"

    def __init__(self) -> None:
        self.shapes: list[tuple[int, int]] = []

    def inpaint(self, rgb: NDArray[np.uint8], mask: NDArray[np.uint8]) -> NDArray[np.uint8]:
        self.shapes.append((rgb.shape[0], rgb.shape[1]))
        return np.full_like(rgb, 7)


def test_outside_mask_bit_identical() -> None:
    img = gradient(200, 240)
    img[60:90, 80:130] = (0, 200, 0)
    mask = rect_mask(200, 240, 80, 60, 130, 90)
    out = inpaint_tiled(img, mask, TeleaInpainter())
    assert np.array_equal(out[mask == 0], img[mask == 0])
    assert not np.array_equal(out[mask > 0], img[mask > 0])


def test_empty_mask_returns_copy() -> None:
    img = gradient(64, 64)
    out = inpaint_tiled(img, np.zeros((64, 64), np.uint8), TeleaInpainter())
    assert np.array_equal(out, img)
    assert out is not img


def test_tiles_merge_when_overlapping() -> None:
    near = rect_mask(400, 400, 100, 100, 110, 110) | rect_mask(400, 400, 140, 100, 150, 110)
    assert len(plan_tiles(near, pad=48)) == 1
    far = rect_mask(400, 400, 10, 10, 20, 20) | rect_mask(400, 400, 380, 380, 390, 390)
    assert len(plan_tiles(far, pad=8)) == 2


def test_tile_sides_multiple_of_8() -> None:
    mask = rect_mask(480, 640, 101, 53, 131, 87) | rect_mask(480, 640, 500, 300, 517, 311)
    tiles = plan_tiles(mask, pad=13)
    assert len(tiles) == 2
    for t in tiles:
        assert t.w % 8 == 0 and t.h % 8 == 0
        assert 0 <= t.x0 < t.x1 <= 640 and 0 <= t.y0 < t.y1 <= 480


def test_tile_at_image_corner_still_multiple_of_8() -> None:
    mask = rect_mask(480, 640, 0, 0, 5, 5)
    (t,) = plan_tiles(mask, pad=13)
    assert (t.x0, t.y0) == (0, 0) and t.w % 8 == 0 and t.h % 8 == 0


def test_wide_tile_is_downscaled() -> None:
    img = gradient(200, 3200)
    mask = rect_mask(200, 3200, 1000, 80, 2000, 120)
    rec = Recorder()
    out = inpaint_tiled(img, mask, rec, max_side=1024)
    assert len(rec.shapes) == 1
    assert max(rec.shapes[0]) <= 1024
    assert all(s % 8 == 0 for s in rec.shapes[0])
    assert out.shape == img.shape
    assert np.array_equal(out[mask == 0], img[mask == 0])


def test_small_tile_not_downscaled() -> None:
    rec = Recorder()
    tiles: list[Tile] = []
    inpaint_tiled(
        gradient(200, 200),
        rect_mask(200, 200, 90, 90, 110, 110),
        rec,
        on_tile=lambda t, _s: tiles.append(t),
    )
    assert rec.shapes == [(tiles[0].h, tiles[0].w)]


def test_telea_reduces_error_against_clean_plate() -> None:
    clean = gradient(160, 200)
    img = clean.copy()
    mask = rect_mask(160, 200, 70, 50, 120, 100)
    img[mask > 0] = (0, 180, 0)
    out = inpaint_tiled(img, mask, TeleaInpainter())
    sel = mask > 0
    err_before = np.abs(img[sel].astype(int) - clean[sel]).mean()
    err_after = np.abs(out[sel].astype(int) - clean[sel]).mean()
    assert err_after < err_before / 3


def test_mask_across_tile_boundary_matches_untiled() -> None:
    """A component wider than the tile padding is filled as one tile: no seam versus untiled."""
    clean = gradient(160, 320)
    img = clean.copy()
    mask = rect_mask(160, 320, 40, 60, 280, 100)
    img[mask > 0] = (0, 180, 0)
    tiled = inpaint_tiled(img, mask, TeleaInpainter(), pad=48, feather_px=0)
    untiled = TeleaInpainter().inpaint(img, mask)
    diff = np.abs(tiled.astype(int) - untiled.astype(int))
    assert diff.max() <= 2
    assert np.array_equal(tiled[mask == 0], img[mask == 0])
    # no step across the middle of the mask compared with the untiled neighbour columns
    col_step = np.abs(np.diff(tiled[80, 100:220].astype(int), axis=0)).max()
    assert col_step <= np.abs(np.diff(untiled[80, 100:220].astype(int), axis=0)).max() + 2


def test_two_separate_tiles_match_untiled() -> None:
    clean = gradient(200, 400)
    img = clean.copy()
    mask = rect_mask(200, 400, 40, 80, 70, 110) | rect_mask(200, 400, 300, 80, 330, 110)
    img[mask > 0] = (0, 180, 0)
    tiled = inpaint_tiled(img, mask, TeleaInpainter(), pad=24, feather_px=0)
    untiled = TeleaInpainter().inpaint(img, mask)
    assert np.abs(tiled.astype(int) - untiled.astype(int)).max() <= 2


def test_feather_keeps_outside_unchanged_and_is_deterministic() -> None:
    img = gradient(120, 120)
    mask = rect_mask(120, 120, 40, 40, 70, 70)
    a = inpaint_tiled(img, mask, TeleaInpainter(), feather_px=6)
    b = inpaint_tiled(img, mask, TeleaInpainter(), feather_px=6)
    assert np.array_equal(a, b)
    assert np.array_equal(a[mask == 0], img[mask == 0])


def test_input_validation() -> None:
    with pytest.raises(ConfigError):
        inpaint_tiled(np.zeros((8, 8), np.uint8), np.zeros((8, 8), np.uint8), TeleaInpainter())
    with pytest.raises(ConfigError):
        inpaint_tiled(np.zeros((8, 8, 3), np.uint8), np.zeros((4, 4), np.uint8), TeleaInpainter())


def test_parse_frames() -> None:
    assert parse_frames(None) is None
    assert parse_frames("2-5") == (2, 5)
    assert parse_frames("3") == (3, 3)
    for bad in ("x", "5-2", "-1-3"):
        with pytest.raises(ConfigError):
            parse_frames(bad)


def test_models_lock_records_source() -> None:
    entry = load_models_lock()["big-lama"]
    for key in ("url", "licence", "source_project", "input", "sha256"):
        assert key in entry
    assert entry["input"]["size_multiple"] == 8


def _lock(tmp_path: Path, sha: str | None) -> Path:
    p = tmp_path / "lock.json"
    p.write_text(json.dumps({"big-lama": {"sha256": sha}}), encoding="utf-8")
    return p


def test_check_weights(tmp_path: Path) -> None:
    w = tmp_path / "w.pt"
    w.write_bytes(b"abc")
    good = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    check_weights(w, _lock(tmp_path, good), trust_unlisted=False)
    with pytest.raises(ConfigError, match="does not match"):
        check_weights(w, _lock(tmp_path, "0" * 64), trust_unlisted=False)
    with pytest.raises(ConfigError, match="no sha256"):
        check_weights(w, _lock(tmp_path, None), trust_unlisted=False)
    check_weights(w, _lock(tmp_path, None), trust_unlisted=True)
    with pytest.raises(ConfigError, match="not found"):
        check_weights(tmp_path / "missing.pt", _lock(tmp_path, good), trust_unlisted=False)


def _session(tmp_path: Path, n: int = 2) -> Path:
    root = tmp_path / "s"
    new_session(root, {})
    lines = []
    for i in range(n):
        img = gradient(96, 128)
        mask = rect_mask(96, 128, 40, 30, 70, 60)
        img[mask > 0] = (0, 180, 0)
        write_image(root / "frames" / f"{i:06d}.png", img)
        write_mask(
            root / "masks" / "m", i, MaskSet(union=mask, labels=(mask > 0).astype(np.uint16))
        )
        lines.append(json.dumps({"idx": i, "t_ns": i, "color": f"frames/{i:06d}.png"}))
    (root / "frames.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def test_command_telea(tmp_path: Path) -> None:
    root = _session(tmp_path)
    args = ["inpaint", "--session", str(root), "--mask", "m", "--backend", "telea", "--no-log-file"]
    assert cli.main([*args, "--frames", "1-1"]) == 0
    assert not (root / "inpaint" / "m-telea" / "000000.png").exists()
    assert (root / "inpaint" / "m-telea" / "000001.png").is_file()
    timing = json.loads((root / "metrics" / "inpaint-m-telea-timing.json").read_text("utf-8"))
    assert timing["device"] == "cpu" and timing["tiles_per_frame"] == 1 and timing["frames"] == 1
    assert cli.main(args) == 0
    assert (root / "inpaint" / "m-telea" / "000000.png").is_file()


def test_command_no_frames_selected(tmp_path: Path) -> None:
    root = _session(tmp_path)
    rc = cli.main(
        [
            "inpaint",
            "--session",
            str(root),
            "--mask",
            "m",
            "--backend",
            "telea",
            "--frames",
            "50-60",
            "--no-log-file",
        ]
    )
    assert rc != 0


def test_lama_without_torch_gives_clear_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import builtins

    real = builtins.__import__

    def fake(name: str, *a: object, **k: object) -> object:
        if name == "torch":
            raise ImportError("no torch")
        return real(name, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(ConfigError, match="needs torch"):
        LamaInpainter(tmp_path / "w.pt")


def test_lama_smoke() -> None:
    pytest.importorskip("torch")
    weights = Path(__file__).resolve().parents[3] / "data" / "fx" / "models" / "big-lama.pt"
    if not weights.is_file():
        pytest.skip("LaMa weights not downloaded (data/fx/models/big-lama.pt)")
    lama = LamaInpainter(weights, "cpu", trust_unlisted_checksum=True)
    img = gradient(64, 80)
    mask = rect_mask(64, 80, 20, 20, 40, 40)
    out = lama.inpaint(img, mask)
    assert out.shape == img.shape and out.dtype == np.uint8
