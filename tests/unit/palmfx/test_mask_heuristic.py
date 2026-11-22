"""FX-011: heuristic blob masks on the synthetic scene (plan 08, A8).

The blob look here is the synthetic one from ``palmfx.offline.synth`` (flat olive boxes), not a
claim about what MSFS renders; real-capture thresholds are VERIFY items tuned in FX-019.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import yaml
from numpy.typing import NDArray

from palmcore.errors import ConfigError
from palmfx.offline import cli
from palmfx.offline.mask_heuristic import (
    DEFAULT_CONFIG,
    HeuristicParams,
    debug_overlay,
    heuristic_masks,
)
from palmfx.offline.mask_metrics import iou, match_instances
from palmfx.offline.session import read_mask
from palmfx.offline.synth import (
    HIT_BUILDING,
    SynthFrame,
    SynthScene,
    default_intrinsics,
    render_sequence,
    trajectory,
)

from .conftest import SYNTH_FPS, SYNTH_PALMS_ENU, SYNTH_SPEED_MPS


@pytest.fixture(scope="module")
def params() -> HeuristicParams:
    return HeuristicParams.from_yaml()


def test_iou_against_ground_truth(synth_seq: list[SynthFrame], params: HeuristicParams) -> None:
    for f in synth_seq:
        ms = heuristic_masks(f.color, f.depth_raw, params)
        assert iou(ms.union, f.gt.union) >= 0.7
        # Nothing is detected that is not a blob, and most blobs are found.
        res = match_instances(ms.labels, f.gt.labels, 0.3)
        assert res.fp == 0
        assert res.tp >= 4  # the farthest blob shows only a few protruding rows (known limit)


def test_building_is_rejected(synth_frame: SynthFrame, params: HeuristicParams) -> None:
    ms = heuristic_masks(synth_frame.color, synth_frame.depth_raw, params)
    on_building = (ms.union > 0) & (synth_frame.hit_id == HIT_BUILDING)
    assert not on_building.any()
    # A scene with only the building gives nothing.
    scene = SynthScene(palms_enu=np.zeros((0, 2)), seed=7)
    rows = trajectory(1, SYNTH_SPEED_MPS, 1000.0 / SYNTH_FPS)
    f = render_sequence(scene, rows, default_intrinsics())[0]
    assert (f.hit_id == HIT_BUILDING).any()
    empty = heuristic_masks(f.color, f.depth_raw, params, debug=True)
    assert empty.instances == []
    assert not empty.union.any()


def _flat_lawn(h: int = 180, w: int = 320) -> tuple[NDArray[np.uint8], NDArray[np.float32]]:
    """Green ground with a smooth depth ramp: matches the colour test but nothing protrudes."""
    color = np.zeros((h, w, 3), dtype=np.uint8)
    color[:] = (72, 112, 52)
    rows = np.linspace(0.02, 0.004, h, dtype=np.float32)[:, None]
    return color, np.repeat(rows, w, axis=1)


def test_flat_green_lawn_is_rejected(params: HeuristicParams) -> None:
    color, depth = _flat_lawn()
    ms = heuristic_masks(color, depth, params, debug=True)
    assert ms.instances == []
    assert ms.params["debug"]["candidate_px"] == 0


def test_green_patch_that_protrudes_but_is_wide_is_rejected(params: HeuristicParams) -> None:
    color, depth = _flat_lawn()
    depth = depth.copy()
    depth[60:110, 100:260] *= 1.5  # nearer, but far wider than the opening
    ms = heuristic_masks(color, depth, params, debug=True)
    assert ms.instances == []


def test_short_green_protrusion_gets_a_reason(params: HeuristicParams) -> None:
    color, depth = _flat_lawn()
    depth = depth.copy()
    depth[100:102, 150:156] *= 1.6  # tiny, nearer, green
    ms = heuristic_masks(color, depth, params, debug=True)
    assert ms.instances == []
    comps = ms.params["debug"]["components"]
    assert comps
    assert all(c["reasons"] for c in comps)
    assert any("height" in c["reasons"] for c in comps)


def test_thresholds_scale_with_image_height(params: HeuristicParams) -> None:
    scene = SynthScene(palms_enu=SYNTH_PALMS_ENU, seed=7)
    rows = trajectory(1, SYNTH_SPEED_MPS, 1000.0 / SYNTH_FPS)
    counts = []
    for scale in (1, 2):
        k = default_intrinsics(320 * scale, 180 * scale)
        f = render_sequence(scene, rows, k)[0]
        ms = heuristic_masks(f.color, f.depth_raw, params)
        counts.append(len(ms.instances))
        assert iou(ms.union, f.gt.union) >= 0.65  # a little lower at 2x: 1 px dilation
    assert counts[0] == counts[1] >= 4


def test_not_reversed_depth(synth_frame: SynthFrame, params: HeuristicParams) -> None:
    d = synth_frame.depth_raw.astype(np.float64)
    inverted = np.where(d > 0, 0.01 / np.where(d > 0, d, 1.0), 0.0).astype(np.float32)
    ms = heuristic_masks(synth_frame.color, inverted, params, reversed=False)
    assert iou(ms.union, synth_frame.gt.union) >= 0.7
    assert ms.params["reversed"] is False


def test_occluder_is_removed(synth_frame: SynthFrame, params: HeuristicParams) -> None:
    base = heuristic_masks(synth_frame.color, synth_frame.depth_raw, params)
    x0, y0, x1, y1 = base.instances[0]["bbox"]
    occ = np.zeros(base.union.shape, dtype=np.uint8)
    occ[y0 : y1 + 1, x0 : x1 + 1] = 255
    ms = heuristic_masks(synth_frame.color, synth_frame.depth_raw, params, occluder=occ)
    assert not ms.union[occ > 0].any()
    assert ms.union.sum() < base.union.sum()


def test_deterministic_and_labelled(synth_frame: SynthFrame, params: HeuristicParams) -> None:
    a = heuristic_masks(synth_frame.color, synth_frame.depth_raw, params)
    b = heuristic_masks(synth_frame.color, synth_frame.depth_raw, params)
    assert np.array_equal(a.labels, b.labels)
    assert a.labels.dtype == np.uint16
    assert sorted(int(v) for v in np.unique(a.labels) if v) == list(range(1, len(a.instances) + 1))
    assert all(i["palm_id"] is None for i in a.instances)
    assert a.method == "heuristic"


def test_every_rejection_has_a_reason(synth_frame: SynthFrame, params: HeuristicParams) -> None:
    ms = heuristic_masks(synth_frame.color, synth_frame.depth_raw, params, debug=True)
    comps = ms.params["debug"]["components"]
    assert comps
    for c in comps:
        assert c["kept"] == (not c["reasons"])
        assert c["reason"] == (c["reasons"][0] if c["reasons"] else None)
    assert any(not c["kept"] for c in comps)  # the farthest blob in this scene
    overlay = debug_overlay(synth_frame.color, ms)
    assert overlay.shape == synth_frame.color.shape
    assert not np.array_equal(overlay, synth_frame.color)


def test_thresholds_come_from_yaml(synth_frame: SynthFrame, params: HeuristicParams) -> None:
    doc = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    assert set(doc) == {f.name for f in dataclasses.fields(HeuristicParams)}
    strict = dataclasses.replace(params, min_height_px=10_000.0)
    assert heuristic_masks(synth_frame.color, synth_frame.depth_raw, strict).instances == []
    off = dataclasses.replace(params, regrow_depth_tol=0.0)
    without = heuristic_masks(synth_frame.color, synth_frame.depth_raw, off)
    with_regrow = heuristic_masks(synth_frame.color, synth_frame.depth_raw, params)
    assert without.union.sum() < with_regrow.union.sum()


def test_bad_config_and_inputs(tmp_path: Path, params: HeuristicParams) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("protrusion_min: 0.1\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="missing keys"):
        HeuristicParams.from_yaml(bad)
    doc = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    doc["hue_min"] = 100
    bad.write_text(yaml.safe_dump(doc), encoding="utf-8")
    with pytest.raises(ConfigError, match="hue"):
        HeuristicParams.from_yaml(bad)
    with pytest.raises(ConfigError, match="cannot read"):
        HeuristicParams.from_yaml(tmp_path / "missing.yaml")
    color, depth = _flat_lawn()
    with pytest.raises(ConfigError, match="shape"):
        heuristic_masks(color, depth[:10], params)
    with pytest.raises(ConfigError, match="uint8"):
        heuristic_masks(color.astype(np.float32), depth, params)
    with pytest.raises(ConfigError, match="occluder"):
        heuristic_masks(color, depth, params, occluder=np.zeros((3, 3), dtype=np.uint8))


def test_cli_writes_masks_and_compares_with_gt(
    synth_session_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "session"
    shutil.copytree(synth_session_dir, root)
    assert cli.main(["ingest", "--session", str(root), "--offset-ms", "40"]) == 0
    assert cli.main(["mask-heuristic", "--session", str(root), "--debug"]) == 0
    out = root / "masks" / "heuristic"
    assert (out / "000000.png").is_file()
    assert (out / "000000.inst.png").is_file()
    assert (out / "debug" / "000000.png").is_file()
    doc = json.loads((out / "000000.json").read_text(encoding="utf-8"))
    assert doc["method"] == "heuristic"
    assert "debug" in doc["params"]
    assert read_mask(out, 0).union.any()

    capsys.readouterr()
    args = ["mask-compare", "--session", str(root), "--a", "heuristic", "--b", "gt"]
    assert cli.main(args) == 0
    path = root / "metrics" / "mask-heuristic-vs-gt.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    assert metrics["summary"]["frames_compared"] == 8
    assert metrics["summary"]["pixel_iou_mean"] >= 0.7


def test_cli_rejects_bad_reversed_flag(synth_session_dir: Path, tmp_path: Path) -> None:
    root = tmp_path / "session"
    shutil.copytree(synth_session_dir, root)
    assert cli.main(["ingest", "--session", str(root), "--offset-ms", "40"]) == 0
    meta_path = root / "session.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["reversed"] = "yes"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    assert cli.main(["mask-heuristic", "--session", str(root)]) != 0
