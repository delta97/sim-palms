"""palmfx.offline.mask_project and the mask-project command on the synthetic scene (plan 08, A7)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from palmcore.errors import ConfigError
from palmfx.offline import cli
from palmfx.offline.camera import CameraPose, Intrinsics
from palmfx.offline.mask_metrics import compare_dirs
from palmfx.offline.mask_project import (
    ProjectParams,
    fill_ground_elev,
    load_palms,
    palm_billboard,
    palm_record,
    palms_to_enu,
    project_masks,
)
from palmfx.offline.session import read_mask
from palmfx.offline.synth import (
    SYNTH_FRAME,
    SynthScene,
    default_intrinsics,
    make_palms_geojson,
    render_sequence,
    trajectory,
    write_fake_session,
)

# Tuned for the synthetic 4 x 4 x 12 m boxes at 320 x 180; the defaults target real 1440 p blobs.
SYNTH_PARAMS = {"dilate_px": 0, "width_scale": 1.2, "top_extra_m": 1.0, "min_width_m": 4.0}
N = 8
SYNTH_PALMS_ENU = [(6.0, -8.0), (-14.0, 10.0), (22.0, -25.0), (-30.0, -15.0), (10.0, 40.0)]


def _posed_session(
    root: Path, scene: SynthScene, n_frames: int = N, *, with_depth: bool = True
) -> Path:
    """A fake session plus ``frames.jsonl`` (canonical poses) and metric ``depth.npy`` files."""
    write_fake_session(root, scene, n_frames=n_frames, fps=30.0, speed_mps=30.0)
    K = default_intrinsics()
    rows = trajectory(n_frames, 30.0, 1000.0 / 30.0)
    frames = render_sequence(scene, rows, K)
    (root / "frames").mkdir(exist_ok=True)
    lines = []
    for f, row in zip(frames, rows, strict=True):
        stem = f"{f.idx:06d}"
        depth_rel = None
        if with_depth:
            depth_rel = f"frames/{stem}.depth.npy"
            np.save(root / depth_rel, np.asarray(f.depth_m, dtype=np.float32))
        pose = {k: row[k] for k in ("lat_deg", "lon_deg", "alt_msl_m", "pitch_deg", "bank_deg")}
        pose["heading_deg"] = row["heading_true_deg"]
        lines.append(
            json.dumps(
                {
                    "idx": f.idx,
                    "t_ns": f.t_ns,
                    "color": f"frames/{stem}.color.png",
                    "depthraw": None,
                    "depth": depth_rel,
                    "pose": pose,
                    "pose_gap_ms": 0.0,
                }
            )
        )
    (root / "frames.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return root


def _run(session: Path, *extra: str) -> int:
    return cli.main(
        [
            "mask-project",
            "--session",
            str(session),
            "--palms",
            str(session / "palms.geojson"),
            "--params",
            json.dumps(SYNTH_PARAMS),
            *extra,
        ]
    )


@pytest.fixture(scope="module")
def projected(synth_scene: SynthScene, tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _posed_session(tmp_path_factory.mktemp("proj") / "20260101-SYN-low-01", synth_scene)
    assert _run(root) == 0
    return root


def test_depth_masks_match_ground_truth(projected: Path) -> None:
    result = compare_dirs(projected / "masks" / "project-depth", projected / "masks" / "gt")
    rows = result["frames"]
    assert len(rows) == N
    worst = min(r["pixel_iou"] for r in rows)
    assert worst >= 0.85, [round(r["pixel_iou"], 3) for r in rows]
    assert result["summary"]["recall"] > 0.9


def test_both_sets_carry_palm_ids_and_defaults(projected: Path) -> None:
    for method in ("project-raw", "project-depth"):
        ms = read_mask(projected / "masks" / method, 0)
        assert ms.method == method
        assert ms.instances
        for inst in ms.instances:
            assert inst["palm_id"].startswith("syn-")
            assert inst["defaulted"] == []
            assert inst["elev_estimated"] is False
            assert inst["z_m"] > 0
            assert set(inst) >= {"bbox", "area_px", "base_uv", "top_uv", "k"}
        assert int(ms.labels.max()) <= len(ms.instances) + 5
        assert (ms.union > 0).sum() == (ms.labels > 0).sum()


def test_summary_written(projected: Path) -> None:
    doc = json.loads((projected / "metrics" / "mask-project-summary.json").read_text("utf-8"))
    assert doc["frames_written"] == N
    assert doc["frames_with_depth_masks"] == N
    assert len(doc["frames"]) == N
    assert set(doc["skipped_total"]) >= {"behind_camera", "off_screen", "too_small"}


def test_raw_matches_ground_truth_without_occluder(tmp_path: Path) -> None:
    scene = SynthScene(palms_enu=SYNTH_PALMS_ENU, building=None, seed=1)
    root = _posed_session(tmp_path / "20260101-SYN-low-01", scene, 4)
    assert _run(root) == 0
    result = compare_dirs(root / "masks" / "project-raw", root / "masks" / "gt")
    assert min(r["pixel_iou"] for r in result["frames"]) >= 0.85


def test_palm_behind_building_removed_by_depth_test(tmp_path: Path) -> None:
    # A building 40 m high stands between the camera and the palm.
    scene = SynthScene(palms_enu=[(0.0, 30.0)], building=((-10.0, -5.0), (10.0, 5.0), 60.0), seed=2)
    root = _posed_session(tmp_path / "20260101-SYN-low-01", scene, 2)
    assert _run(root) == 0
    gt = read_mask(root / "masks" / "gt", 0)
    assert not gt.instances  # fully hidden in the ground truth
    raw = read_mask(root / "masks" / "project-raw", 0)
    dep = read_mask(root / "masks" / "project-depth", 0)
    assert len(raw.instances) == 1
    assert int((dep.union > 0).sum()) == 0
    assert dep.instances == []
    summary = json.loads((root / "metrics" / "mask-project-summary.json").read_text("utf-8"))
    assert summary["frames"][0]["palms_in_view"] == 1
    assert summary["frames"][0]["palms_in_view_depth"] == 0


def test_no_depth_test_writes_only_raw(tmp_path: Path, projected: Path) -> None:
    root = tmp_path / "copy"
    shutil.copytree(projected, root)
    shutil.rmtree(root / "masks" / "project-raw")
    shutil.rmtree(root / "masks" / "project-depth")
    assert _run(root, "--no-depth-test") == 0
    assert (root / "masks" / "project-raw" / "000000.png").is_file()
    assert not (root / "masks" / "project-depth").exists()


def test_missing_depth_writes_only_raw(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scene = SynthScene(palms_enu=[(0.0, 10.0)], building=None)
    root = _posed_session(tmp_path / "20260101-SYN-low-01", scene, 2, with_depth=False)
    assert _run(root) == 0
    assert (root / "masks" / "project-raw" / "000001.png").is_file()
    assert not (root / "masks" / "project-depth").exists()
    assert "no metric depth" in capsys.readouterr().out


def _camera_at(position: tuple[float, float, float], heading_deg: float = 0.0) -> CameraPose:
    """Level camera looking along +n (heading 0) or -n (heading 180); OpenCV axes."""
    sign = 1.0 if heading_deg == 0.0 else -1.0
    # camera x = east*sign, y = down, z = forward (north*sign)
    r = np.array([[sign, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, sign, 0.0]])
    return CameraPose(position_enu=np.array(position), R_cam_from_enu=r)


def _palm(e: float, n: float, **kw: Any) -> dict[str, Any]:
    p = palm_record(kw.pop("palm_id", f"syn-{int(n)}"), 0.0, 0.0, kw or {"height_m": 12.0})
    p["enu_base"] = [e, n, 0.0]
    return p


def test_nearer_palm_wins_overlap() -> None:
    K = default_intrinsics()
    pose = _camera_at((0.0, 0.0, 10.0))
    far = _palm(3.0, 80.0, palm_id="syn-far", height_m=12.0, crown_diam_m=4.0)
    near = _palm(0.0, 40.0, palm_id="syn-near", height_m=12.0, crown_diam_m=4.0)
    params = ProjectParams.from_mapping(SYNTH_PARAMS)
    alone_far = project_masks([far], K, pose, None, params).raw.union > 0
    alone_near = project_masks([near], K, pose, None, params).raw.union > 0
    overlap = alone_far & alone_near
    assert overlap.any()  # the test is only meaningful if the billboards share pixels
    for order in ([far, near], [near, far]):
        res = project_masks(order, K, pose, None, params)
        by_id = {i["palm_id"]: i for i in res.raw.instances}
        k_near, k_far = by_id["syn-near"]["k"], by_id["syn-far"]["k"]
        assert np.all(res.raw.labels[overlap] == k_near)
        assert np.array_equal(res.raw.labels == k_near, alone_near)
        assert np.array_equal(res.raw.labels == k_far, alone_far & ~alone_near)


def test_palm_behind_camera_and_off_screen_skipped() -> None:
    K = default_intrinsics()
    pose = _camera_at((0.0, 0.0, 10.0))
    params = ProjectParams.from_mapping(SYNTH_PARAMS)
    behind = _palm(0.0, -30.0, palm_id="syn-behind", height_m=12.0)
    side = _palm(500.0, 30.0, palm_id="syn-side", height_m=12.0)
    far = _palm(0.0, 5000.0, palm_id="syn-far", height_m=12.0)
    tiny = _palm(0.0, 1400.0, palm_id="syn-tiny", height_m=1.0)
    visible = _palm(0.0, 30.0, palm_id="syn-visible", height_m=12.0)
    res = project_masks([behind, side, far, tiny, visible], K, pose, None, params)
    assert [i["palm_id"] for i in res.raw.instances] == ["syn-visible"]
    assert res.skipped["behind_camera"] == 1
    assert res.skipped["off_screen"] == 1
    assert res.skipped["out_of_range"] == 1
    assert res.skipped["too_small"] == 1
    assert res.in_view == 1
    assert res.depth is None


def test_billboard_faces_camera() -> None:
    pose = _camera_at((0.0, 0.0, 10.0))
    palm = _palm(30.0, 40.0, palm_id="syn-x", height_m=12.0, crown_diam_m=4.0)
    quad = palm_billboard(palm, pose, ProjectParams())
    base = np.array([30.0, 40.0, 0.0])
    to_base = base - pose.position_enu
    edge = quad[1] - quad[0]
    assert abs(float(edge @ to_base)) < 1e-9  # perpendicular to the line of sight
    assert edge[2] == 0.0
    assert np.isclose(np.linalg.norm(edge), max(4.0, 1.3 * 4.0))
    assert np.isclose(quad[2][2], 12.0 + 1.0)


def test_missing_height_defaults_and_is_flagged() -> None:
    p = palm_record("syn-0", 0.0, 0.0, {"crown_diam_m": 5.0})
    assert p["height_m"] == 12.0
    assert p["crown_diam_m"] == 5.0
    assert p["defaulted"] == ["height_m"]
    q = palm_record("syn-1", 0.0, 0.0, {"height_m": None, "crown_diam_m": 0})
    assert q["defaulted"] == ["height_m", "crown_diam_m"]
    assert (q["height_m"], q["crown_diam_m"]) == (12.0, 4.0)


def test_defaulted_flag_reaches_instance_json(tmp_path: Path) -> None:
    scene = SynthScene(palms_enu=[(0.0, 15.0)], building=None)
    root = _posed_session(tmp_path / "20260101-SYN-low-01", scene, 2)
    doc = make_palms_geojson(scene)
    for feat in doc["features"]:
        del feat["properties"]["height_m"]
        feat["properties"]["ground_elev_m"] = None
    palms_path = root / "palms-lenient.geojson"
    palms_path.write_text(json.dumps(doc), encoding="utf-8")
    code = cli.main(
        ["mask-project", "--session", str(root), "--palms", str(palms_path),
         "--lenient-palms", "--ground-elev-m", "0.0",
         "--params", json.dumps(SYNTH_PARAMS)]
    )  # fmt: skip
    assert code == 0
    inst = read_mask(root / "masks" / "project-raw", 0).instances[0]
    assert inst["defaulted"] == ["height_m"]
    assert inst["elev_estimated"] is True
    summary = json.loads((root / "metrics" / "mask-project-summary.json").read_text("utf-8"))
    assert summary["palms_defaulted"] == 1
    assert summary["palms_elev_estimated"] == 1


def test_null_ground_elev_uses_median_then_fallback() -> None:
    a = palm_record("syn-a", 0.0, 0.0, {"ground_elev_m": 10.0})
    b = palm_record("syn-b", 0.0, 0.0, {"ground_elev_m": 30.0})
    c = palm_record("syn-c", 0.0, 0.0, {"ground_elev_m": None})
    out = fill_ground_elev([a, b, c], fallback_m=99.0)
    assert out[2]["ground_elev_m"] == 20.0
    assert out[2]["elev_estimated"] is True
    assert out[0]["elev_estimated"] is False
    only_null = fill_ground_elev([c], fallback_m=7.5)
    assert only_null[0]["ground_elev_m"] == 7.5
    with pytest.raises(ConfigError):
        fill_ground_elev([c], None)


def test_load_palms_strict_reads_contract_file(tmp_path: Path) -> None:
    scene = SynthScene(palms_enu=[(0.0, 15.0), (5.0, 30.0)], building=None)
    path = tmp_path / "palms.geojson"
    path.write_text(json.dumps(make_palms_geojson(scene)), encoding="utf-8")
    palms = load_palms(path)
    assert [p["palm_id"] for p in palms] == [scene.palm_id(0), scene.palm_id(1)]
    assert all(p["defaulted"] == [] and p["ground_elev_m"] is not None for p in palms)
    enu = palms_to_enu(palms, SYNTH_FRAME)
    assert np.allclose(enu[0]["enu_base"][:2], [0.0, 15.0], atol=0.05)


def test_static_occluder_removed_and_unknown_param_rejected() -> None:
    K = Intrinsics.from_vfov(320, 180, 50.0)
    pose = _camera_at((0.0, 0.0, 10.0))
    palm = _palm(0.0, 30.0, palm_id="syn-p", height_m=12.0)
    params = ProjectParams.from_mapping(SYNTH_PARAMS)
    base = project_masks([palm], K, pose, None, params)
    occ = np.zeros((180, 320), dtype=np.uint8)
    occ[:, :160] = 255
    cut = project_masks([palm], K, pose, None, params, occ)
    assert int((cut.raw.union > 0).sum()) < int((base.raw.union > 0).sum())
    assert not np.any((cut.raw.union > 0) & (occ > 0))
    with pytest.raises(ConfigError):
        ProjectParams.from_mapping({"nope": 1})


def test_deterministic(tmp_path: Path) -> None:
    scene = SynthScene(palms_enu=[(0.0, 15.0), (6.0, 30.0)], building=None, seed=3)
    root = _posed_session(tmp_path / "20260101-SYN-low-01", scene, 2)
    assert _run(root) == 0
    first = (root / "masks" / "project-depth" / "000001.inst.png").read_bytes()
    assert _run(root) == 0
    assert (root / "masks" / "project-depth" / "000001.inst.png").read_bytes() == first


def test_reads_calib_files_written_by_palmfx_calib(tmp_path: Path) -> None:
    """mask-project takes vfov from calib/intrinsics.json and the bias from pose_bias.json
    (the names `palmfx calib`, FX-009, writes). A wrong vfov there must change the masks."""
    scene = SynthScene(palms_enu=SYNTH_PALMS_ENU, building=None, seed=1)
    meta_vfov = None
    scores = {}
    for label, scale in (("true", 1.0), ("wrong", 1.6)):
        root = _posed_session(tmp_path / label / "20260101-SYN-low-01", scene, 4)
        meta = json.loads((root / "session.json").read_text(encoding="utf-8"))
        meta_vfov = float(meta["synthetic"]["vfov_deg"])
        calib = root / "calib"
        calib.mkdir(exist_ok=True)
        (calib / "intrinsics.json").write_text(
            json.dumps({"vfov_deg": meta_vfov * scale}), encoding="utf-8"
        )
        (calib / "pose_bias.json").write_text(
            json.dumps(
                {
                    "d_heading_deg": 0.0,
                    "d_pitch_deg": 0.0,
                    "d_bank_deg": 0.0,
                    "d_body_m": [0.0, 0.0, 0.0],
                }
            ),
            encoding="utf-8",
        )
        assert _run(root) == 0
        result = compare_dirs(root / "masks" / "project-raw", root / "masks" / "gt")
        scores[label] = min(r["pixel_iou"] for r in result["frames"])
    assert meta_vfov is not None
    assert scores["true"] >= 0.85
    assert scores["wrong"] < scores["true"] - 0.2
