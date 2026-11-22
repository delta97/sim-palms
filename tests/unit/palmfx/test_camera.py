from __future__ import annotations

import numpy as np
import pytest

from palmfx.offline.camera import (
    CAM_FROM_BODY,
    ENU_FROM_NED,
    CameraPose,
    Intrinsics,
    LocalFrame,
    R_ned_from_body,
    backproject,
    pose_from_simvars,
    project,
)

FRAME = LocalFrame(32.79, -117.25, 50.0)
K = Intrinsics.from_vfov(1920, 1080, 60.0)


def row(**kw: float) -> dict[str, float]:
    base = {
        "lat_deg": 32.79,
        "lon_deg": -117.25,
        "alt_msl_m": 50.0,
        "heading_true_deg": 0.0,
        "pitch_deg": 0.0,
        "bank_deg": 0.0,
    }
    base.update(kw)
    return base


def pose_at(**kw: float) -> CameraPose:
    return pose_from_simvars(row(**kw), FRAME, [0, 0, 0], {})


def test_enu_round_trip_5km() -> None:
    rng = np.random.default_rng(1)
    enu = rng.uniform(-5000, 5000, (200, 3))
    enu[:, 2] = rng.uniform(-100, 500, 200)
    lat, lon, h = FRAME.from_enu(enu)
    back = FRAME.to_enu(lat, lon, h)
    assert np.abs(back - enu).max() < 1e-3


def test_origin_and_axes() -> None:
    assert np.allclose(FRAME.to_enu(32.79, -117.25, 50.0), 0, atol=1e-6)
    north = FRAME.to_enu(32.791, -117.25, 50.0)[0]
    east = FRAME.to_enu(32.79, -117.249, 50.0)[0]
    up = FRAME.to_enu(32.79, -117.25, 60.0)[0]
    assert north[1] > 100 and abs(north[0]) < 1
    assert east[0] > 90 and abs(east[1]) < 1
    assert up[2] == pytest.approx(10.0, abs=1e-6)


def test_rotation_matrices_are_proper() -> None:
    r = R_ned_from_body(33, -12, 25)
    assert np.allclose(r @ r.T, np.eye(3))
    assert np.linalg.det(r) == pytest.approx(1.0)
    assert np.linalg.det(ENU_FROM_NED) == pytest.approx(1.0)
    assert np.linalg.det(CAM_FROM_BODY) == pytest.approx(1.0)


def test_attitude_signs() -> None:
    assert (R_ned_from_body(0, 10, 0) @ [1, 0, 0])[2] < 0  # nose up: NED z negative
    assert (R_ned_from_body(0, 0, 10) @ [0, 1, 0])[2] > 0  # right wing down
    east = R_ned_from_body(90, 0, 0) @ [1, 0, 0]
    assert np.allclose(east, [0, 1, 0], atol=1e-12)


def test_point_ahead_below() -> None:
    uv, z = project([[0, 100, -10]], pose_at(), K)
    assert z[0] == pytest.approx(100.0)
    assert uv[0, 0] == pytest.approx(K.cx)
    assert uv[0, 1] > K.cy
    assert uv[0, 1] == pytest.approx(K.cy + K.fy * 10 / 100)


def test_principal_point_straight_ahead() -> None:
    uv, z = project([[0, 250, 0]], pose_at(), K)
    assert uv[0] == pytest.approx([K.cx, K.cy])
    assert z[0] == pytest.approx(250.0)


def test_heading_east() -> None:
    uv, z = project([[200, 0, 0]], pose_at(heading_true_deg=90.0), K)
    assert uv[0] == pytest.approx([K.cx, K.cy], abs=1e-9)
    assert z[0] == pytest.approx(200.0)


def test_point_to_the_right_is_right() -> None:
    uv, _ = project([[10, 100, 0]], pose_at(), K)
    assert uv[0, 0] > K.cx


def test_pitch_up_moves_point_down_and_sign_flip() -> None:
    p = [[0, 100, 0]]
    base, _ = project(p, pose_at(), K)
    up, _ = project(p, pose_at(pitch_deg=10.0), K)
    assert up[0, 1] > base[0, 1]
    assert up[0, 1] - K.cy == pytest.approx(K.fy * np.tan(np.radians(10)), rel=1e-9)
    flipped = pose_from_simvars(row(pitch_deg=-10.0), FRAME, [0, 0, 0], {"pitch_sign": -1})
    uv2, _ = project(p, flipped, K)
    assert uv2 == pytest.approx(up)


def test_bank_and_heading_sign_flip() -> None:
    p = [[5, 100, 3]]
    a, _ = project(p, pose_at(bank_deg=7.0, heading_true_deg=3.0), K)
    conv = {"bank_sign": -1, "heading_sign": -1}
    b_pose = pose_from_simvars(row(bank_deg=-7.0, heading_true_deg=-3.0), FRAME, [0, 0, 0], conv)
    b, _ = project(p, b_pose, K)
    assert b == pytest.approx(a)


def test_right_bank_rotates_scene_counter_clockwise() -> None:
    # A point above the line of sight shifts left in the image when the right wing drops.
    p = [[0, 100, 20]]
    level, _ = project(p, pose_at(), K)
    banked, _ = project(p, pose_at(bank_deg=10.0), K)
    assert banked[0, 0] < level[0, 0]


def test_bias_adds_after_signs() -> None:
    conv = {"pitch_sign": -1}
    biased = pose_from_simvars(row(pitch_deg=-4.0), FRAME, [0, 0, 0], conv, {"d_pitch_deg": 6.0})
    ref = pose_at(pitch_deg=10.0)
    assert biased.R_cam_from_enu == pytest.approx(ref.R_cam_from_enu)


def test_camera_offset_up_shifts_projection() -> None:
    pose = pose_from_simvars(row(), FRAME, [0, 0, -2.0], {})
    assert pose.position_enu == pytest.approx([0, 0, 2.0], abs=1e-6)
    uv, _ = project([[0, 100, 0]], pose, K)
    assert uv[0, 1] - K.cy == pytest.approx(K.fy * 2 / 100)


def test_offset_rotates_with_heading_and_body_bias() -> None:
    pose = pose_from_simvars(row(heading_true_deg=90.0), FRAME, [3.0, 0, 0], {})
    assert pose.position_enu == pytest.approx([3.0, 0, 0], abs=1e-6)
    pose = pose_from_simvars(row(), FRAME, [0, 1.5, 0], {}, {"d_body_m": [2.0, 0, 0]})
    assert pose.position_enu == pytest.approx([1.5, 2.0, 0], abs=1e-6)


def test_camera_relative_yaw_and_pitch() -> None:
    uv, _ = project([[100, 0, 0]], pose_at(cam_yaw_deg=90.0), K)  # right of nose = east
    assert uv[0] == pytest.approx([K.cx, K.cy], abs=1e-9)
    target = [[0, 100, 100 * np.tan(np.radians(10))]]
    uv, _ = project(target, pose_at(cam_pitch_deg=10.0), K)
    assert uv[0] == pytest.approx([K.cx, K.cy], abs=1e-9)


def test_behind_camera_is_nan() -> None:
    uv, z = project([[0, -50, 0], [0, 0, 0]], pose_at(), K)
    assert np.isnan(uv).all()
    assert z[0] == pytest.approx(-50.0)
    assert z[1] == pytest.approx(0.0)


def test_project_backproject_round_trip() -> None:
    rng = np.random.default_rng(7)
    pose = pose_from_simvars(
        row(heading_true_deg=123.0, pitch_deg=-8.0, bank_deg=4.0, cam_yaw_deg=5.0),
        FRAME,
        [1.0, 0.5, -1.0],
        {},
    )
    cam_pts = rng.uniform([-30, -20, 20], [30, 20, 800], (100, 3))
    pts = pose.position_enu + cam_pts @ pose.R_cam_from_enu
    uv, z = project(pts, pose, K)
    assert (z > 0).all()
    assert np.abs(backproject(uv, z, pose, K) - pts).max() < 1e-6


def test_intrinsics_from_vfov() -> None:
    k = Intrinsics.from_vfov(1920, 1080, 90.0)
    assert k.fx == pytest.approx(540.0)
    assert (k.cx, k.cy) == (960.0, 540.0)
    with pytest.raises(Exception, match="vfov"):
        Intrinsics.from_vfov(10, 10, 0)


def test_heading_key_alias_and_missing_key() -> None:
    r = row()
    r["heading_deg"] = r.pop("heading_true_deg")
    pose_from_simvars(r, FRAME, [0, 0, 0], {})
    del r["heading_deg"]
    with pytest.raises(Exception, match="heading"):
        pose_from_simvars(r, FRAME, [0, 0, 0], {})
