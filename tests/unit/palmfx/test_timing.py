"""palmfx.offline.timing: pose interpolation."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from palmfx.offline.camera import LocalFrame
from palmfx.offline.timing import interpolate_poses, interpolate_poses_with_gap

MS = 1_000_000
LAT0, LON0, ALT0 = 32.79, -117.25, 60.0


def _row(t_ms: float, e: float, heading: float, **extra: float) -> dict[str, Any]:
    frame = LocalFrame(LAT0, LON0, ALT0)
    lat, lon, alt = frame.from_enu(np.array([[e, 0.5 * e, 0.0]]))
    return {
        "t_host_ns": int(t_ms * MS),
        "lat_deg": float(lat[0]),
        "lon_deg": float(lon[0]),
        "alt_msl_m": float(alt[0]),
        "heading_true_deg": heading % 360.0,
        "pitch_deg": 3.0,
        "bank_deg": -2.0,
        **extra,
    }


def _linear_rows() -> list[dict[str, Any]]:
    # 100 Hz samples, 20 m/s east and 10 m/s north, heading 10 deg/s from 350 deg (wraps at 1 s).
    return [_row(t, 20.0 * t / 1000.0, 350.0 + 10.0 * t / 1000.0) for t in range(0, 2001, 10)]


def test_exact_on_linear_motion() -> None:
    rows = _linear_rows()
    times_ms = np.array([5.0, 123.4, 777.7, 1000.0, 1500.5])
    poses = interpolate_poses(rows, (times_ms * MS).astype(np.int64))
    frame = LocalFrame(LAT0, LON0, ALT0)
    for t, pose in zip(times_ms, poses, strict=True):
        assert pose is not None
        enu = frame.to_enu(pose["lat_deg"], pose["lon_deg"], pose["alt_msl_m"])[0]
        assert abs(enu[0] - 20.0 * t / 1000.0) < 0.01
        assert abs(enu[1] - 10.0 * t / 1000.0) < 0.01
        assert abs(enu[2]) < 0.01
        dh = (pose["heading_deg"] - (350.0 + 10.0 * t / 1000.0) + 180.0) % 360.0 - 180.0
        assert abs(dh) < 0.01
        assert abs(pose["pitch_deg"] - 3.0) < 0.01
        assert abs(pose["bank_deg"] + 2.0) < 0.01


def test_heading_wraps_through_zero() -> None:
    rows = [_row(0, 0.0, 359.0), _row(100, 1.0, 1.0)]
    pose = interpolate_poses(rows, np.array([50 * MS]))[0]
    assert pose is not None
    dh = (pose["heading_deg"] + 180.0) % 360.0 - 180.0
    assert abs(dh) < 0.01  # 0 deg, not 180
    assert 0.0 <= pose["heading_deg"] < 360.0


def test_gap_returns_none_with_gap_ms() -> None:
    rows = [_row(0, 0.0, 10.0), _row(1000, 10.0, 20.0)]
    out = interpolate_poses_with_gap(rows, np.array([40 * MS, 500 * MS, 960 * MS]), 50)
    assert out[0][0] is not None and out[0][1] == pytest.approx(40.0)
    assert out[1][0] is None and out[1][1] == pytest.approx(500.0)
    assert out[2][0] is not None and out[2][1] == pytest.approx(40.0)


def test_outside_range_holds_within_gap_else_none() -> None:
    rows = [_row(100, 2.0, 10.0), _row(200, 4.0, 20.0)]
    before, after, far = interpolate_poses(rows, np.array([80 * MS, 240 * MS, 400 * MS]), 50)
    assert before is not None and after is not None and far is None
    assert before["heading_deg"] == pytest.approx(10.0, abs=1e-6)
    assert after["heading_deg"] == pytest.approx(20.0, abs=1e-6)


def test_conventions_applied_and_unsorted_duplicates_ignored() -> None:
    rows = [_row(100, 1.0, 10.0), _row(0, 0.0, 10.0), _row(100, 99.0, 10.0)]
    pose = interpolate_poses(rows, np.array([0]), 50, {"pitch_sign": -1, "bank_sign": -1})[0]
    assert pose is not None
    assert pose["pitch_deg"] == pytest.approx(-3.0, abs=1e-6)
    assert pose["bank_deg"] == pytest.approx(2.0, abs=1e-6)
    mid = interpolate_poses(rows, np.array([50 * MS]), 50)[0]
    assert mid is not None  # first duplicate (e = 1) wins, so no 99 m jump
    enu = LocalFrame(LAT0, LON0, ALT0).to_enu(mid["lat_deg"], mid["lon_deg"], mid["alt_msl_m"])[0]
    assert enu[0] == pytest.approx(0.5, abs=0.01)


def test_cam_columns_interpolate_on_circle() -> None:
    rows = [_row(0, 0, 0.0, cam_yaw_deg=170.0), _row(100, 1, 0.0, cam_yaw_deg=-170.0)]
    pose = interpolate_poses(rows, np.array([50 * MS]))[0]
    assert pose is not None
    assert abs(abs(pose["cam_yaw_deg"]) - 180.0) < 1e-9


def test_empty_and_single_sample() -> None:
    assert interpolate_poses([], np.array([0])) == [None]
    one = interpolate_poses([_row(0, 0.0, 5.0)], np.array([10 * MS, 90 * MS]), 50)
    assert one[0] is not None and one[1] is None


def test_deterministic() -> None:
    rows = _linear_rows()
    t = np.array([123 * MS, 456 * MS])
    assert interpolate_poses(rows, t) == interpolate_poses(rows, t)
