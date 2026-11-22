"""Camera model: geodesy, aircraft attitude and pinhole projection (plan 08, A5).

World frame is a local ENU tangent plane. Heights are treated as MSL for both poses and palms.
Camera axes follow OpenCV (x right, y down, z forward).

Canonical attitude signs: heading true, clockwise from north; pitch positive nose up; bank
positive right wing down. Raw SimVars pass through ``conventions`` first.

VERIFY: the signs of the real SimVars (FX-006), whether the sim FOV setting is vertical or
horizontal (FX-006/FX-009), and the meaning of camera SimVars (``cam_pitch_deg``,
``cam_yaw_deg``). Nothing here is confirmed against MSFS 2024.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from pyproj import Transformer

Array = NDArray[np.float64]

_GEODETIC_TO_ECEF = Transformer.from_crs("EPSG:4979", "EPSG:4978", always_xy=True)
_ECEF_TO_GEODETIC = Transformer.from_crs("EPSG:4978", "EPSG:4979", always_xy=True)

# (e, n, u) = (y_n, x_n, -z_d)
ENU_FROM_NED: Array = np.array([[0.0, 1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, -1.0]])
# Camera x = body right, y = body down, z = body forward (body axes: forward, right, down).
CAM_FROM_BODY: Array = np.array([[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])


@dataclass(frozen=True)
class Intrinsics:
    """Square-pixel pinhole intrinsics."""

    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float

    @classmethod
    def from_vfov(cls, width: int, height: int, vfov_deg: float) -> Intrinsics:
        """Intrinsics for a vertical field of view, principal point at the image centre."""
        if not 0.0 < vfov_deg < 180.0:
            raise ValueError(f"vfov_deg must be in (0, 180), got {vfov_deg}")
        f = (height / 2.0) / np.tan(np.radians(vfov_deg) / 2.0)
        return cls(width, height, float(f), float(f), width / 2.0, height / 2.0)


@dataclass(frozen=True)
class CameraPose:
    """Camera position in ENU and rotation taking ENU vectors to camera axes."""

    position_enu: Array
    R_cam_from_enu: Array


class LocalFrame:
    """ENU tangent frame at (lat0, lon0, h0), built on pyproj geodetic to ECEF."""

    def __init__(self, lat0: float, lon0: float, h0: float) -> None:
        self.lat0, self.lon0, self.h0 = float(lat0), float(lon0), float(h0)
        x, y, z = _GEODETIC_TO_ECEF.transform(self.lon0, self.lat0, self.h0)
        self._origin: Array = np.array([x, y, z], dtype=np.float64)
        la, lo = np.radians(self.lat0), np.radians(self.lon0)
        sl, cl, so, co = np.sin(la), np.cos(la), np.sin(lo), np.cos(lo)
        self._R_enu_from_ecef: Array = np.array(
            [[-so, co, 0.0], [-sl * co, -sl * so, cl], [cl * co, cl * so, sl]]
        )

    def to_enu(self, lat: ArrayLike, lon: ArrayLike, h: ArrayLike) -> Array:
        """Geodetic (deg, deg, m) to ENU metres, shape (N, 3)."""
        lat_a, lon_a, h_a = np.broadcast_arrays(
            np.atleast_1d(np.asarray(lat, dtype=np.float64)),
            np.atleast_1d(np.asarray(lon, dtype=np.float64)),
            np.atleast_1d(np.asarray(h, dtype=np.float64)),
        )
        x, y, z = _GEODETIC_TO_ECEF.transform(lon_a.ravel(), lat_a.ravel(), h_a.ravel())
        ecef = np.stack([x, y, z], axis=1) - self._origin
        out: Array = ecef @ self._R_enu_from_ecef.T
        return out

    def from_enu(self, enu: ArrayLike) -> tuple[Array, Array, Array]:
        """ENU metres (N, 3) to (lat, lon, h), each shape (N,)."""
        pts = np.atleast_2d(np.asarray(enu, dtype=np.float64))
        ecef = pts @ self._R_enu_from_ecef + self._origin
        lon, lat, h = _ECEF_TO_GEODETIC.transform(ecef[:, 0], ecef[:, 1], ecef[:, 2])
        return (
            np.asarray(lat, dtype=np.float64),
            np.asarray(lon, dtype=np.float64),
            np.asarray(h, dtype=np.float64),
        )


def _rx(a: float) -> Array:
    c, s = np.cos(a), np.sin(a)
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])


def _ry(a: float) -> Array:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def _rz(a: float) -> Array:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def R_ned_from_body(heading_deg: float, pitch_deg: float, bank_deg: float) -> Array:
    """Aerospace ZYX rotation ``Rz(heading) Ry(pitch) Rx(bank)``, canonical signs.

    Body axes are forward, right, down. Pitch positive nose up and bank positive right wing
    down both follow from this rotation order with body z pointing down.
    """
    out: Array = (
        _rz(np.radians(heading_deg)) @ _ry(np.radians(pitch_deg)) @ _rx(np.radians(bank_deg))
    )
    return out


def _first(row: Mapping[str, float], *keys: str) -> float:
    for k in keys:
        if k in row and row[k] is not None:
            return float(row[k])
    raise ValueError(f"pose row lacks any of {keys}")


def pose_from_simvars(
    row: Mapping[str, float],
    frame: LocalFrame,
    cam_offset_body_m: Sequence[float],
    conventions: Mapping[str, float] | None = None,
    bias: Mapping[str, float] | None = None,
) -> CameraPose:
    """Camera pose from an aircraft pose row.

    ``row`` holds ``lat_deg``, ``lon_deg``, ``alt_msl_m``, ``heading_true_deg`` (or
    ``heading_deg``), ``pitch_deg``, ``bank_deg`` and optionally ``cam_pitch_deg`` (up positive)
    and ``cam_yaw_deg`` (right positive), both relative to the body.
    ``conventions`` holds ``pitch_sign``, ``bank_sign``, ``heading_sign`` (each +-1, default 1)
    applied to the raw angles. ``bias`` holds ``d_heading_deg``, ``d_pitch_deg``,
    ``d_bank_deg`` (added after the signs) and ``d_body_m`` ([f, r, d]).
    VERIFY: sign conventions and camera SimVar semantics (FX-006).
    """
    conv = conventions or {}
    b = bias or {}
    heading = conv.get("heading_sign", 1) * _first(row, "heading_true_deg", "heading_deg")
    pitch = conv.get("pitch_sign", 1) * _first(row, "pitch_deg")
    bank = conv.get("bank_sign", 1) * _first(row, "bank_deg")
    heading += b.get("d_heading_deg", 0.0)
    pitch += b.get("d_pitch_deg", 0.0)
    bank += b.get("d_bank_deg", 0.0)

    r_enu_from_body = ENU_FROM_NED @ R_ned_from_body(heading, pitch, bank)

    offset = np.asarray(cam_offset_body_m, dtype=np.float64).reshape(3)
    offset = offset + np.asarray(b.get("d_body_m", (0.0, 0.0, 0.0)), dtype=np.float64).reshape(3)
    p_ac = frame.to_enu(_first(row, "lat_deg"), _first(row, "lon_deg"), _first(row, "alt_msl_m"))[0]
    position = p_ac + r_enu_from_body @ offset

    cam_pitch = float(row.get("cam_pitch_deg") or 0.0)
    cam_yaw = float(row.get("cam_yaw_deg") or 0.0)
    # Camera relative to the body, in body FRD: yaw right about down, pitch up about right.
    r_body_from_cam_body = _rz(np.radians(cam_yaw)) @ _ry(np.radians(cam_pitch))
    r_cam_from_enu: Array = CAM_FROM_BODY @ r_body_from_cam_body.T @ r_enu_from_body.T
    return CameraPose(position_enu=position, R_cam_from_enu=r_cam_from_enu)


def project(points_enu: ArrayLike, pose: CameraPose, K: Intrinsics) -> tuple[Array, Array]:
    """Project ENU points to pixels. Returns ``(uv (N,2), z (N,))``; ``z <= 0`` gives NaN uv."""
    pts = np.atleast_2d(np.asarray(points_enu, dtype=np.float64))
    cam = (pts - pose.position_enu) @ pose.R_cam_from_enu.T
    z = cam[:, 2]
    ok = z > 0.0
    safe = np.where(ok, z, 1.0)
    uv = np.stack([K.fx * cam[:, 0] / safe + K.cx, K.fy * cam[:, 1] / safe + K.cy], axis=1)
    uv[~ok] = np.nan
    return uv, z


def backproject(uv: ArrayLike, z: ArrayLike, pose: CameraPose, K: Intrinsics) -> Array:
    """Pixels plus camera-frame depth ``z`` to ENU points (N, 3)."""
    uv_a = np.atleast_2d(np.asarray(uv, dtype=np.float64))
    z_a = np.atleast_1d(np.asarray(z, dtype=np.float64))
    cam = np.stack(
        [(uv_a[:, 0] - K.cx) / K.fx * z_a, (uv_a[:, 1] - K.cy) / K.fy * z_a, z_a], axis=1
    )
    out: Array = cam @ pose.R_cam_from_enu + pose.position_enu
    return out
