"""palmfx ingest and fixture: end to end on a small fake session built inline."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from palmcore.errors import ConfigError
from palmfx.offline import cli
from palmfx.offline.camera import LocalFrame
from palmfx.offline.commands.fixture import build_fixture, sample_nearest
from palmfx.offline.depth import pack_log24, unpack_log24
from palmfx.offline.ingest import ingest
from palmfx.offline.session import new_session, open_session, read_image, write_image

MS = 1_000_000
W, H = 64, 48
N = 6
T0 = 5_000_000_000
STEP_MS = 133
LAT0, LON0, ALT0 = 32.79, -117.25, 60.0


def _truth(t_ns: int) -> tuple[np.ndarray, float]:
    t = (t_ns - T0) / 1e9
    return np.array([20.0 * t, 10.0 * t, 0.0]), (355.0 + 10.0 * t) % 360.0


def _depth(i: int) -> np.ndarray:
    d = np.linspace(0.01, 0.9, W * H, dtype=np.float64).reshape(H, W) * (1.0 + 0.01 * i)
    d[:5, :] = 0.0  # sky
    return d


def make_session(root: Path, *, pose_until_ms: float = 2000.0, hand: bool = False) -> Path:
    frame = LocalFrame(LAT0, LON0, ALT0)
    meta = {"site": "fake", "simvar_conventions": {}, "resolution": [W, H]}
    s = new_session(root, meta)
    rng = np.random.default_rng(3)
    reshade = s.path("raw", "reshade")
    reshade.mkdir(parents=True)
    with s.path("raw", "triggers.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["frame_idx", "t_trigger_ns"])
        for i in range(N):
            w.writerow([i, T0 + i * STEP_MS * MS])
    for i in range(N):
        write_image(reshade / f"shot{i:03d}_before.png", rng.integers(0, 255, (H, W, 3), np.uint8))
        write_image(reshade / f"shot{i:03d}_after.png", pack_log24(_depth(i)))
    header = ["t_host_ns", "sim_time_s", "lat_deg", "lon_deg", "alt_msl_m"]
    header += ["heading_true_deg", "pitch_deg", "bank_deg"]
    with s.path("raw", "poses.csv").open("w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for ms in range(0, int(pose_until_ms) + 1, 10):
            t_ns = T0 - 500 * MS + ms * MS
            enu, hdg = _truth(t_ns)
            lat, lon, alt = frame.from_enu(enu[None, :])
            row = [t_ns, ms / 1000, f"{lat[0]:.12f}", f"{lon[0]:.12f}", f"{alt[0]:.6f}"]
            w.writerow([*row, f"{hdg:.9f}", "3.0", "-2.0"])
    if hand:
        intr = {"width": W, "height": H, "fx": 80.0, "fy": 80.0, "cx": 32.0, "cy": 24.0}
        s.path("calib", "intrinsics.json").write_text(json.dumps(intr))
        occ = np.zeros((H, W), np.uint8)
        occ[-8:, :] = 255
        write_image(s.path("calib", "static_occluder.png"), occ)
        for i in range(N):
            m = np.zeros((H, W), np.uint8)
            m[10:20, 8 * i : 8 * i + 6] = 255
            write_image(s.path("masks", "hand", f"{i:06d}.png"), m)
        feats = [
            {
                "type": "Feature",
                "properties": {"palm_id": pid},
                "geometry": {"type": "Point", "coordinates": [LON0, lat]},
            }
            for pid, lat in (("near", LAT0 + 0.001), ("far", LAT0 + 0.5))
        ]
        doc = {"type": "FeatureCollection", "features": feats}
        (root / "palms_src.geojson").write_text(json.dumps(doc))
    return root


def test_ingest_reproduces_truth(tmp_path: Path) -> None:
    root = make_session(tmp_path / "s")
    session = open_session(root)
    assert ingest(session) == N
    frames = session.frames()
    assert [f.idx for f in frames] == list(range(N))
    frame = LocalFrame(LAT0, LON0, ALT0)
    for f in frames:
        assert f.pose is not None and f.pose_gap_ms is not None
        enu, hdg = _truth(f.t_ns)
        got = frame.to_enu(f.pose["lat_deg"], f.pose["lon_deg"], f.pose["alt_msl_m"])[0]
        assert np.linalg.norm(got - enu) < 0.01
        assert abs(f.pose["heading_deg"] - hdg) < 0.01
        assert abs(f.pose["pitch_deg"] - 3.0) < 0.01 and abs(f.pose["bank_deg"] + 2.0) < 0.01
        assert f.depthraw is not None and f.depth is None
        raw = np.load(f.depthraw)
        assert raw.dtype == np.float32 and raw.shape == (H, W)
        expect = unpack_log24(pack_log24(_depth(f.idx)))
        assert np.allclose(raw, expect, rtol=1e-6)
        assert (raw[:5] == 0).all()
        assert read_image(f.color).shape == (H, W, 3)
    assert frames[2].t_ns == T0 + 2 * STEP_MS * MS


def test_heading_wrap_in_frames(tmp_path: Path) -> None:
    session = open_session(make_session(tmp_path / "s"))
    ingest(session)
    headings = [f.pose["heading_deg"] for f in session.frames() if f.pose]
    assert any(h > 355 for h in headings) and any(h < 5 for h in headings)


def test_missing_pose_when_log_ends(tmp_path: Path) -> None:
    session = open_session(make_session(tmp_path / "s", pose_until_ms=900.0))
    ingest(session, max_gap_ms=50)
    frames = session.frames()
    assert frames[0].pose is not None and frames[-1].pose is None
    gap = frames[-1].pose_gap_ms
    assert gap is not None and gap > 50


def test_mismatch_raises_and_drop_recovers(tmp_path: Path) -> None:
    root = make_session(tmp_path / "s")
    (root / "raw" / "reshade" / "shot002_before.png").unlink()
    (root / "raw" / "reshade" / "shot002_after.png").unlink()
    session = open_session(root)
    with pytest.raises(ConfigError, match=r"5 screenshot pairs but 6 triggers.*--drop"):
        ingest(session)
    assert ingest(session, drop=[2]) == N - 1
    assert [f.idx for f in session.frames()] == [0, 1, 3, 4, 5]
    with pytest.raises(ConfigError, match="not in triggers"):
        ingest(session, drop=[99])


def test_time_offset_file_and_override(tmp_path: Path) -> None:
    root = make_session(tmp_path / "s")
    session = open_session(root)
    (root / "calib" / "time_offset.json").write_text(json.dumps({"offset_ms": 20.0, "rms_px": 1}))
    ingest(session)
    assert session.frames()[0].t_ns == T0 + 20 * MS
    ingest(session, offset_ms=0.0)
    assert session.frames()[0].t_ns == T0


def test_custom_suffixes_and_columns(tmp_path: Path) -> None:
    root = make_session(tmp_path / "s")
    for p in (root / "raw" / "reshade").iterdir():
        p.rename(p.with_name(p.name.replace("_before", "-c").replace("_after", "-d")))
    text = (root / "raw" / "poses.csv").read_text().replace("heading_true_deg", "hdg")
    (root / "raw" / "poses.csv").write_text(text)
    session = open_session(root)
    with pytest.raises(ConfigError, match="missing columns"):
        ingest(session, before_suffix="-c", after_suffix="-d")
    n = ingest(session, before_suffix="-c", after_suffix="-d", columns={"heading_true_deg": "hdg"})
    assert n == N


def test_cli_ingest(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_session(tmp_path / "s")
    assert cli.main(["ingest", "--session", str(root), "--no-log-file", "--max-gap-ms", "40"]) == 0
    assert f"ingested {N} frames" in capsys.readouterr().out
    assert cli.main(["ingest", "--session", str(root), "--no-log-file", "--drop", "x"]) == 2


def test_fixture_roundtrip(tmp_path: Path) -> None:
    root = make_session(tmp_path / "src", hand=True)
    out = tmp_path / "sample-seq"
    build_fixture(open_session(root), out, [1, 3, 5], 0.5, palms=root / "palms_src.geojson")
    assert sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) < 5 * 1024 * 1024

    meta = json.loads((out / "session.json").read_text())
    assert meta["source_frames"] == [1, 3, 5] and meta["resolution"] == [W // 2, H // 2]
    intr = json.loads((out / "calib" / "intrinsics.json").read_text())
    assert intr["fx"] == 40.0 and intr["width"] == W // 2 and intr["cy"] == 12.0
    assert read_image(out / "calib" / "static_occluder.png").shape == (H // 2, W // 2)

    # Depth is never interpolated: decoded fixture values are a subset of the source values.
    for new_i, src_i in enumerate([1, 3, 5]):
        small = unpack_log24(read_image(out / "raw" / "reshade" / f"{new_i:06d}_after.png"))
        src = unpack_log24(read_image(root / "raw" / "reshade" / f"shot{src_i:03d}_after.png"))
        assert small.shape == (H // 2, W // 2)
        assert set(np.unique(small)) <= set(np.unique(src))
    hand = read_image(out / "masks" / "hand" / "000001.png")
    assert set(np.unique(hand)) <= {0, 255} and hand.any()

    palms = json.loads((out / "palms.geojson").read_text())
    assert [f["properties"]["palm_id"] for f in palms["features"]] == ["near"]

    with (out / "raw" / "poses.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    with (root / "raw" / "poses.csv").open() as fh:
        src_rows = list(csv.DictReader(fh))
    assert 0 < len(rows) < len(src_rows)

    session = open_session(out)
    assert ingest(session) == 3
    assert [f.idx for f in session.frames()] == [0, 1, 2]
    assert all(f.pose is not None for f in session.frames())
    assert session.frames()[1].t_ns == T0 + 3 * STEP_MS * MS


def test_fixture_enforces_size_limit_and_cleans_up(tmp_path: Path) -> None:
    root = make_session(tmp_path / "src")
    out = tmp_path / "big"
    with pytest.raises(ConfigError, match="over the"):
        build_fixture(open_session(root), out, [0, 1], 1.0, max_bytes=100)
    assert not out.exists()
    with pytest.raises(ConfigError, match="not available"):
        build_fixture(open_session(root), out, [0, 42], 0.5)
    assert not out.exists()


def test_sample_nearest_never_blends() -> None:
    img = np.arange(64, dtype=np.uint8).reshape(8, 8)
    small: Any = sample_nearest(img, 2, 2)
    assert set(small.ravel()) <= set(img.ravel())
