"""Self-tests for tests/visual/diff_score.py: identical runs, a changed block, masks, sizes, errors.

Runs are small folders in a temp dir (same layout as tests/visual/<site>/<date>[_<label>]/).
Images are generated here, never from the sim. Default thresholds are not used for the flag
cases: they are tight test thresholds, so the flags come from the code path being tested.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

from tests.visual.diff_score import THRESHOLDS_FILE, load_thresholds, main
from tests.visual.new_run import VIEWPOINT_FILES

WIDTH, HEIGHT = 400, 300
SITE = "T1"
VPS = tuple(name.split("_", 1)[0] for name in VIEWPOINT_FILES)
TIGHT = {"ssim_min": 0.99, "mad_max": 0.005, "calibrated": False, "noise_floor": None}


def _base(seed: int, width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    """A smooth gradient with mild noise, so SSIM is meaningful and not trivially 0 or 1."""
    rng = np.random.default_rng(seed)
    xs = np.linspace(0, 200, width)
    ys = np.linspace(0, 120, height)
    grad = xs[None, :] + ys[:, None]
    noise = rng.normal(0.0, 6.0, size=(height, width))
    arr = np.clip(grad + 20 + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, mode="L").convert("RGB")


def _block_changed(img: Image.Image) -> Image.Image:
    """Return a copy with a 50 x 50 block at (100, 100) pushed to a strong contrast."""
    out = img.copy()
    block = Image.new("RGB", (50, 50), (255, 255, 255))
    out.paste(block, (100, 100))
    return out


def _write_run(
    tmp: Path,
    name: str,
    images: dict[str, dict[str, Image.Image]],
    *,
    site: str = SITE,
) -> Path:
    run = tmp / "tests" / "visual" / SITE / name
    run.mkdir(parents=True)
    (run / "run.yaml").write_text(
        yaml.safe_dump({"site": site, "variants": list(images)}), encoding="utf-8"
    )
    for variant, by_vp in images.items():
        folder = run / variant
        folder.mkdir()
        for vp, image in by_vp.items():
            file_name = next(n for n in VIEWPOINT_FILES if n.startswith(vp + "_"))
            image.save(folder / file_name, quality=90)
    return run


def _three(seed: int) -> dict[str, Image.Image]:
    return {vp: _base(seed + i) for i, vp in enumerate(VPS)}


def _thresholds_file(tmp: Path, values: dict[str, object] | None = None) -> Path:
    path = tmp / "thresholds.yaml"
    path.write_text(yaml.safe_dump(values or TIGHT), encoding="utf-8")
    return path


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    """Two runs, each with nofix and static. Run B's static has a changed block in VP2 only."""
    base = _three(1)
    run_a = _write_run(tmp_path, "2026-11-22_a", {"nofix": base, "static": base})
    changed = dict(base)
    changed["VP2"] = _block_changed(base["VP2"])
    run_b = _write_run(tmp_path, "2026-11-22_b", {"nofix": base, "static": changed})
    return run_a, run_b


def _scores(run_b: Path) -> dict[str, object]:
    return json.loads((run_b / "diff" / "scores.json").read_text(encoding="utf-8"))


def test_identical_runs_score_one_and_exit_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    images = _three(7)
    run_a = _write_run(tmp_path, "2026-11-22_a", {"static": images})
    run_b = _write_run(tmp_path, "2026-11-22_b", {"static": images})
    rc = main([str(run_a), str(run_b), "--thresholds", str(_thresholds_file(tmp_path))])
    out = capsys.readouterr().out
    assert rc == 0
    assert "FLAGGED" not in out
    assert "1.0000" in out and "0.0000" in out


def test_identical_scores_are_exact(tmp_path: Path) -> None:
    from tests.visual.diff_score import compare_runs, load_thresholds

    images = _three(7)
    run_a = _write_run(tmp_path, "2026-11-22_a", {"static": images})
    run_b = _write_run(tmp_path, "2026-11-22_b", {"static": images})
    thresholds = load_thresholds(_thresholds_file(tmp_path))
    _, scores = compare_runs(
        run_a, run_b, variant_a="static", variant_b="static", thresholds=thresholds
    )
    assert [s.vp for s in scores] == list(VPS)
    for score in scores:
        assert score.ssim == pytest.approx(1.0)
        assert score.mad == pytest.approx(0.0)
        assert not score.flagged
        assert score.compared_size == (WIDTH, HEIGHT)


def test_changed_block_is_flagged_only_in_its_viewpoint(
    tmp_path: Path, pair: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    run_a, run_b = pair
    rc = main(
        [
            str(run_a),
            str(run_b),
            "--variant",
            "static",
            "--thresholds",
            str(_thresholds_file(tmp_path)),
        ]
    )
    out = capsys.readouterr().out
    assert rc == 1
    lines = {line.split()[0]: line for line in out.splitlines() if line[:3] in VPS}
    assert "FLAGGED" in lines["VP2"]
    assert "FLAGGED" not in lines["VP1"]
    assert "FLAGGED" not in lines["VP3"]


def test_mask_excluding_the_block_removes_the_flag(tmp_path: Path, pair: tuple[Path, Path]) -> None:
    run_a, run_b = pair
    site_dir = run_a.parent
    mask = Image.new("L", (WIDTH, HEIGHT), 255)
    # Black (ignore) over the block with a margin, so SSIM windows at the edge are excluded too.
    mask.paste(0, (92, 92, 158, 158))
    mask.save(site_dir / "mask_VP2.png")
    rc = main(
        [
            str(run_a),
            str(run_b),
            "--variant",
            "static",
            "--thresholds",
            str(_thresholds_file(tmp_path)),
        ]
    )
    assert rc == 0


def test_mask_is_recorded_in_scores_json(tmp_path: Path, pair: tuple[Path, Path]) -> None:
    run_a, run_b = pair
    mask = Image.new("L", (WIDTH, HEIGHT), 255)
    mask.paste(0, (92, 92, 158, 158))
    mask.save(run_a.parent / "mask_VP2.png")
    rc = main(
        [
            str(run_a),
            str(run_b),
            "--variant",
            "static",
            "--thresholds",
            str(_thresholds_file(tmp_path)),
            "--write",
        ]
    )
    assert rc == 0
    viewpoints = _scores(run_b)["viewpoints"]
    assert viewpoints["VP2"]["masked"] is True
    assert viewpoints["VP1"]["masked"] is False


def test_write_saves_heatmaps_and_scores(tmp_path: Path, pair: tuple[Path, Path]) -> None:
    run_a, run_b = pair
    rc = main(
        [
            str(run_a),
            str(run_b),
            "--variant",
            "static",
            "--thresholds",
            str(_thresholds_file(tmp_path)),
            "--write",
        ]
    )
    assert rc == 1
    for vp in VPS:
        heat = run_b / "diff" / f"{vp}_heatmap.png"
        assert heat.is_file()
        with Image.open(heat) as img:
            assert img.size == (WIDTH, HEIGHT)
    document = _scores(run_b)
    assert document["flagged"] is True
    assert document["viewpoints"]["VP2"]["flagged"] is True
    assert document["viewpoints"]["VP1"]["flagged"] is False
    assert document["thresholds"]["calibrated"] is False


def test_different_image_sizes_compare_at_the_smaller_size(tmp_path: Path) -> None:
    base = _three(3)
    small = {vp: img.resize((200, 150), Image.Resampling.LANCZOS) for vp, img in base.items()}
    run_a = _write_run(tmp_path, "2026-11-22_a", {"static": base})
    run_b = _write_run(tmp_path, "2026-11-22_b", {"static": small})
    # Default-like thresholds: the resize path, not the tight flags, is what is tested here.
    thresholds = _thresholds_file(
        tmp_path, {"ssim_min": 0.90, "mad_max": 0.05, "calibrated": False, "noise_floor": None}
    )
    rc = main([str(run_a), str(run_b), "--thresholds", str(thresholds), "--write"])
    assert rc == 0
    for vp in VPS:
        assert _scores(run_b)["viewpoints"][vp]["compared_size"] == [200, 150]


def test_missing_viewpoint_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    images = _three(5)
    run_a = _write_run(tmp_path, "2026-11-22_a", {"static": images})
    (run_a / "static" / "VP2_oblique.jpg").unlink()
    run_b = _write_run(tmp_path, "2026-11-22_b", {"static": images})
    rc = main([str(run_a), str(run_b), "--thresholds", str(_thresholds_file(tmp_path))])
    assert rc == 2
    assert "VP2_oblique.jpg" in capsys.readouterr().err


def test_different_sites_exit_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    images = _three(5)
    run_a = _write_run(tmp_path, "2026-11-22_a", {"static": images})
    run_b = _write_run(tmp_path, "2026-11-22_b", {"static": images}, site="T2")
    rc = main([str(run_a), str(run_b), "--thresholds", str(_thresholds_file(tmp_path))])
    assert rc == 2
    assert "different sites" in capsys.readouterr().err


def test_variant_b_option_compares_different_folders(tmp_path: Path) -> None:
    images = _three(9)
    run_a = _write_run(tmp_path, "2026-11-22_a", {"nofix": images})
    run_b = _write_run(tmp_path, "2026-11-22_b", {"static": images})
    thresholds = _thresholds_file(tmp_path)
    assert (
        main(
            [
                str(run_a),
                str(run_b),
                "--variant",
                "nofix",
                "--variant-b",
                "static",
                "--thresholds",
                str(thresholds),
            ]
        )
        == 0
    )
    # Without --variant-b the default is the same folder name, which RUN_B does not have.
    assert (
        main([str(run_a), str(run_b), "--variant", "nofix", "--thresholds", str(thresholds)]) == 2
    )


def test_unknown_variant_exits_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    images = _three(9)
    run_a = _write_run(tmp_path, "2026-11-22_a", {"static": images})
    run_b = _write_run(tmp_path, "2026-11-22_b", {"static": images})
    rc = main(
        [
            str(run_a),
            str(run_b),
            "--variant",
            "bogus",
            "--thresholds",
            str(_thresholds_file(tmp_path)),
        ]
    )
    assert rc == 2
    assert "variant must be one of" in capsys.readouterr().err


def test_missing_scikit_image_exits_two_with_a_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    images = _three(9)
    run_a = _write_run(tmp_path, "2026-11-22_a", {"static": images})
    run_b = _write_run(tmp_path, "2026-11-22_b", {"static": images})
    monkeypatch.setitem(sys.modules, "skimage.metrics", None)
    rc = main([str(run_a), str(run_b), "--thresholds", str(_thresholds_file(tmp_path))])
    assert rc == 2
    err = capsys.readouterr().err
    assert "scikit-image" in err and "pip install" in err


def test_thresholds_file_missing_key_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    images = _three(9)
    run_a = _write_run(tmp_path, "2026-11-22_a", {"static": images})
    run_b = _write_run(tmp_path, "2026-11-22_b", {"static": images})
    bad = _thresholds_file(tmp_path, {"ssim_min": 0.9, "mad_max": 0.05, "calibrated": False})
    rc = main([str(run_a), str(run_b), "--thresholds", str(bad)])
    assert rc == 2
    assert "noise_floor" in capsys.readouterr().err


def test_repo_thresholds_file_is_provisional() -> None:
    thresholds = load_thresholds(THRESHOLDS_FILE)
    assert thresholds.ssim_min == pytest.approx(0.90)
    assert thresholds.mad_max == pytest.approx(0.05)
    assert thresholds.calibrated is False
    assert thresholds.noise_floor is None


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--help"])
    assert info.value.code == 0
    assert "--variant-b" in capsys.readouterr().out
