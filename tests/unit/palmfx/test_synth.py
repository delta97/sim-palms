"""palmfx.offline.synth: synthetic scene, ground truth and fake session."""

from __future__ import annotations

import csv
import time
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial import ConvexHull

from palmcore.errors import ConfigError
from palmfx.offline.camera import Intrinsics, backproject, pose_from_simvars, project
from palmfx.offline.depth import read_depth_png, unpack_log24
from palmfx.offline.session import open_session, read_image, read_mask
from palmfx.offline.synth import (
    HIT_BUILDING,
    HIT_PALM0,
    MAX_RANGE_M,
    SYNTH_FRAME,
    SynthFrame,
    SynthScene,
    box_corners,
    camera_pose,
    default_intrinsics,
    make_palms_geojson,
    render,
    render_sequence,
    to_raw_row,
    trajectory,
    write_fake_session,
)
from tests.helpers.contract import validate_palms

SESSION_OFFSET_MS = 40.0
SESSION_CONVENTIONS = {"pitch_sign": -1.0}


def _hull_pixel_mask(corners_uv: np.ndarray, shape: tuple[int, int], eps: float) -> np.ndarray:
    """Pixels whose centres are inside (eps > 0 grows, eps < 0 shrinks) the corner hull."""
    hull = ConvexHull(corners_uv)
    h, w = shape
    jj, ii = np.mgrid[0:h, 0:w]
    pts = np.stack([ii.ravel() + 0.5, jj.ravel() + 0.5], axis=1)
    # hull.equations: n . x + c <= 0 inside, with unit normals.
    d = pts @ hull.equations[:, :2].T + hull.equations[:, 2]
    return (np.max(d, axis=1) <= eps).reshape(h, w)


def test_box_silhouette_matches_camera_project(
    synth_scene: SynthScene, synth_frame: SynthFrame, synth_K: Intrinsics
) -> None:
    # Palm 3 is not occluded and not clipped: its mask is exactly the projected box silhouette.
    lo, hi = synth_scene.blob_boxes()[3]
    uv, z = project(box_corners(lo, hi), synth_frame.pose, synth_K)
    assert (z > 0).all()
    assert uv[:, 0].min() > 0 and uv[:, 0].max() < synth_K.width
    assert uv[:, 1].min() > 0 and uv[:, 1].max() < synth_K.height
    mask = synth_frame.gt.labels == 4
    outer = _hull_pixel_mask(uv, mask.shape, 1e-6)
    inner = _hull_pixel_mask(uv, mask.shape, -1e-6)
    assert not (mask & ~outer).any()  # nothing rendered outside the projected hull
    assert not (inner & ~mask).any()  # nothing inside it missing
    assert mask.sum() > 50


def test_gt_mask_is_pixels_whose_nearest_hit_is_a_blob(
    synth_scene: SynthScene, synth_frame: SynthFrame
) -> None:
    f = synth_frame
    blob = f.hit_id >= HIT_PALM0
    assert np.array_equal(f.gt.union > 0, blob)
    assert np.array_equal(f.gt.labels > 0, blob)
    assert np.array_equal(f.gt.labels[blob], f.hit_id[blob] - HIT_PALM0 + 1)
    assert [i["palm_id"] for i in f.gt.instances] == [synth_scene.palm_id(i) for i in range(5)]
    for inst in f.gt.instances:
        assert inst["area_px"] == int((f.gt.labels == inst["k"]).sum())
    # The building hides part of palm 0: the nearest hit wins.
    assert (f.hit_id == HIT_BUILDING).any()
    assert f.gt.instances[0]["area_px"] < f.gt.instances[2]["area_px"]
    # Depth of a mask pixel is nearer than the clean plate behind it.
    assert (f.depth_m[blob] < f.clean_depth_m[blob]).all()


def test_clean_differs_from_color_only_inside_masks(synth_seq: list[SynthFrame]) -> None:
    for f in synth_seq:
        diff = np.any(f.color != f.clean, axis=-1)
        assert diff.any()
        assert not (diff & (f.gt.union == 0)).any()
        inside = f.gt.union > 0
        assert diff[inside].mean() > 0.95
        mean = f.color[inside].mean(axis=0)
        assert mean[1] > mean[0] > mean[2]  # olive: green > red > blue


def test_sky_depth_is_zero_and_nan(synth_frame: SynthFrame) -> None:
    sky = synth_frame.hit_id == 0
    assert sky.any()
    assert (synth_frame.depth_raw[sky] == 0).all()
    assert np.isnan(synth_frame.depth_m[sky]).all()
    assert (synth_frame.depth_raw[~sky] > 0).all()
    assert np.isfinite(synth_frame.depth_m[~sky]).all()
    assert synth_frame.depth_m[~sky].max() <= MAX_RANGE_M
    # Reversed-Z synthetic choice d = 0.1 / z.
    np.testing.assert_allclose(
        synth_frame.depth_raw[~sky], 0.1 / synth_frame.depth_m[~sky], rtol=1e-6
    )
    assert synth_frame.color[sky].mean(axis=0)[2] > 200  # light blue


def test_ground_texture_is_world_anchored(
    synth_scene: SynthScene, synth_K: Intrinsics, synth_rows: list[dict[str, float]]
) -> None:
    """Deterministic, and a ground point keeps its patch class when the camera moves."""
    empty = SynthScene(palms_enu=np.zeros((0, 2)), building=None, seed=synth_scene.seed)
    pose0, pose7 = camera_pose(synth_rows[0]), camera_pose(synth_rows[7])
    a = render(empty, pose0, synth_K)
    assert np.array_equal(a.color, render(empty, pose0, synth_K).color)
    c7 = render(empty, pose7, synth_K).color
    checked = 0
    for row, col in ((150, 40), (150, 160), (140, 250), (170, 100), (120, 200)):
        pt = backproject([[col + 0.5, row + 0.5]], a.depth_m[row, col], pose0, synth_K)
        assert abs(pt[0, 2]) < 1e-2  # on the ground plane
        uv7, _ = project(pt, pose7, synth_K)
        j, i = int(uv7[0, 1]), int(uv7[0, 0])
        if not (0 <= j < synth_K.height and 0 <= i < synth_K.width):
            continue
        # Patch class (grass is greener than asphalt) is constant over 20 m cells.
        g0 = int(a.color[row, col, 1]) - int(a.color[row, col, 0]) > 15
        g7 = int(c7[j, i, 1]) - int(c7[j, i, 0]) > 15
        assert g0 == g7
        checked += 1
    assert checked >= 3


def test_seed_changes_texture(synth_K: Intrinsics, synth_rows: list[dict[str, float]]) -> None:
    pose = camera_pose(synth_rows[0])
    a = render(SynthScene(palms_enu=[(0, 0)], seed=1), pose, synth_K)
    b = render(SynthScene(palms_enu=[(0, 0)], seed=2), pose, synth_K)
    assert not np.array_equal(a.color, b.color)


def test_sequence_metadata_and_motion(synth_seq: list[SynthFrame]) -> None:
    assert [f.idx for f in synth_seq] == list(range(8))
    ts = np.asarray([f.t_ns for f in synth_seq], dtype=np.int64)
    np.testing.assert_allclose(np.diff(ts), 1e9 / 30.0, atol=1.0)
    first, last = synth_seq[0].pose.position_enu, synth_seq[7].pose.position_enu
    np.testing.assert_allclose(last - first, [0.0, 30.0 * 7 / 30.0, 0.0], atol=1e-3)
    assert all(f.pose_row is not None for f in synth_seq)


def test_trajectory_rows_and_conventions() -> None:
    rows = trajectory(3, 10.0, 100.0, heading_deg=90.0, start_enu=(5.0, 6.0))
    assert [r["t_host_ns"] - rows[0]["t_host_ns"] for r in rows] == [0, 100_000_000, 200_000_000]
    pts = np.array(
        [SYNTH_FRAME.to_enu(r["lat_deg"], r["lon_deg"], r["alt_msl_m"])[0] for r in rows]
    )
    np.testing.assert_allclose(pts[:, 0], [5.0, 6.0, 7.0], atol=1e-4)  # east
    np.testing.assert_allclose(pts[:, 1], 6.0, atol=1e-4)
    np.testing.assert_allclose(pts[:, 2], 50.0, atol=1e-4)
    conv = {"pitch_sign": -1, "bank_sign": -1}
    raw = to_raw_row(rows[0], conv)
    assert raw["pitch_deg"] == 10.0
    pose = pose_from_simvars(raw, SYNTH_FRAME, (0, 0, 0), conv)
    np.testing.assert_allclose(pose.R_cam_from_enu, camera_pose(rows[0]).R_cam_from_enu, atol=1e-12)
    with pytest.raises(ConfigError):
        trajectory(2, 1.0, 0.0)
    with pytest.raises(ConfigError):
        trajectory(2, 1.0, 10.0, start_enu=(1.0,))


def test_scene_validation() -> None:
    assert SynthScene(palms_enu=np.zeros((0, 2))).n_palms == 0
    with pytest.raises(ConfigError):
        SynthScene(palms_enu=[1.0, 2.0])
    with pytest.raises(ConfigError):
        SynthScene(palms_enu=[(0, 0)], box_size=(4, 0, 12))


def test_palms_geojson_is_valid_and_matches_boxes(synth_scene: SynthScene) -> None:
    doc = make_palms_geojson(synth_scene)
    assert validate_palms(doc) == []
    assert len(doc["features"]) == 5
    p0 = doc["features"][0]["properties"]
    assert p0["palm_id"] == synth_scene.palm_id(0)
    assert (p0["height_m"], p0["crown_diam_m"]) == (12.0, 4.0)
    lon, lat = doc["features"][0]["geometry"]["coordinates"]
    enu = SYNTH_FRAME.to_enu(lat, lon, 0.0)[0]
    np.testing.assert_allclose(enu[:2], synth_scene.palms_enu[0], atol=0.02)
    assert make_palms_geojson(SynthScene(palms_enu=np.zeros((0, 2))))["features"] == []


def test_render_speed(synth_scene: SynthScene, synth_K: Intrinsics) -> None:
    pose = camera_pose(trajectory(1, 30.0, 33.3)[0])
    render(synth_scene, pose, synth_K)  # warm up
    t0 = time.perf_counter()
    render(synth_scene, pose, synth_K)
    assert time.perf_counter() - t0 < 0.5


def test_fake_session_opens_and_is_consistent(synth_session_dir: Path) -> None:
    s = open_session(synth_session_dir)
    assert s.meta["resolution"] == [320, 180]
    assert s.meta["depth_encoding"] == {"kind": "log24", "dmin": 1e-7}
    assert s.meta["simvar_conventions"] == SESSION_CONVENTIONS
    assert s.meta["synthetic"]["time_offset_ms"] == SESSION_OFFSET_MS
    for d in ("raw", "frames", "calib", "masks"):
        assert s.path(d).is_dir()

    with s.path("raw", "triggers.csv").open(encoding="utf-8", newline="") as fh:
        triggers = list(csv.DictReader(fh))
    with s.path("raw", "poses.csv").open(encoding="utf-8", newline="") as fh:
        poses = list(csv.DictReader(fh))
    assert len(triggers) == 8
    assert len(poses) > 3 * 8
    # Pose rate is 3x the frame rate and covers every frame time.
    t_pose = np.array([int(p["t_host_ns"]) for p in poses])
    np.testing.assert_allclose(np.diff(t_pose), 1e9 / 90.0, atol=2.0)
    t_true = np.array([int(t["t_trigger_ns"]) for t in triggers]) + 40_000_000
    assert t_pose[0] < t_true[0] and t_pose[-1] > t_true[-1]
    # SimVar-style sign: raw pitch is -1 * canonical (-10) = +10.
    assert float(poses[0]["pitch_deg"]) == pytest.approx(10.0)


def test_fake_session_images_round_trip(
    synth_session_dir: Path, synth_seq: list[SynthFrame]
) -> None:
    shots = synth_session_dir / "raw" / "reshade"
    assert len(sorted(shots.glob("*.png"))) == 16
    for f in (synth_seq[0], synth_seq[5]):
        base = shots / f"shot_{f.idx:06d}"
        assert np.array_equal(read_image(Path(f"{base}_before.png")), f.color)
        d = read_depth_png(Path(f"{base}_after.png"))
        sky = f.depth_raw == 0
        assert (d[sky] == 0).all()
        np.testing.assert_allclose(d[~sky], f.depth_raw[~sky], rtol=2e-6)
        np.testing.assert_allclose(
            unpack_log24(read_image(Path(f"{base}_after.png")))[~sky], d[~sky]
        )
    m = read_mask(synth_session_dir / "masks" / "gt", 3)
    assert np.array_equal(m.labels, synth_seq[3].gt.labels)
    assert [i["palm_id"] for i in m.instances] == [i["palm_id"] for i in synth_seq[3].gt.instances]


def test_fake_session_poses_recover_frame_poses(
    synth_session_dir: Path, synth_seq: list[SynthFrame]
) -> None:
    """Raw SimVar-style rows plus conventions reproduce the camera pose used for rendering."""
    with (synth_session_dir / "raw" / "poses.csv").open(encoding="utf-8", newline="") as fh:
        poses = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(fh)]
    f = synth_seq[3]  # frame 3 == pose sample 9 (3x rate), up to rounding
    assert f.t_ns is not None
    p = min(poses, key=lambda r: abs(r["t_host_ns"] - f.t_ns))
    assert abs(p["t_host_ns"] - f.t_ns) <= 2
    pose = pose_from_simvars(p, SYNTH_FRAME, (0, 0, 0), SESSION_CONVENTIONS)
    np.testing.assert_allclose(pose.position_enu, f.pose.position_enu, atol=1e-3)
    np.testing.assert_allclose(pose.R_cam_from_enu, f.pose.R_cam_from_enu, atol=1e-9)


def test_write_fake_session_options(tmp_path: Path, synth_K: Intrinsics) -> None:
    scene = SynthScene(palms_enu=[(0.0, 0.0)], building=None)
    root = write_fake_session(tmp_path / "s", scene, n_frames=2, gt_masks=False, K=synth_K)
    assert not (root / "masks" / "gt").exists()
    assert len(render_sequence(scene, trajectory(2, 30, 33.3), default_intrinsics(64, 36))) == 2
    with pytest.raises(ConfigError):
        write_fake_session(tmp_path / "t", scene, n_frames=0)
    with pytest.raises(ConfigError, match="already exists"):
        write_fake_session(tmp_path / "s", scene, n_frames=2)
