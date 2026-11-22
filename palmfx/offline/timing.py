"""Pose interpolation onto frame times (plan 08, A4 step 4).

Input rows are SimConnect pose samples (``poses.csv``) as dicts with ``t_host_ns``, ``lat_deg``,
``lon_deg``, ``alt_msl_m``, ``heading_true_deg`` (or ``heading_deg``), ``pitch_deg``,
``bank_deg`` and optional ``cam_*`` columns. Output poses are canonical: the conventions
(``heading_sign``, ``pitch_sign``, ``bank_sign``) are already applied, so downstream code calls
``camera.pose_from_simvars`` with empty conventions. The camera body offset is not applied here.

Rules (all deterministic):

- Samples are sorted by ``t_host_ns``; rows with a non-finite field are dropped; for duplicate
  timestamps the first row in input order wins.
- Positions are converted to a local ENU frame at the first valid sample and interpolated
  linearly there (never in raw lat/lon).
- Attitude is interpolated as a quaternion (slerp) built from the canonical ZYX angles, so a
  heading going 359 -> 1 deg passes through 0, not 180. Pitch near +-90 deg (gimbal lock) is not
  specially handled; helicopter and aircraft views stay far from it.
- ``cam_*`` columns ending in ``_deg`` are interpolated along the shortest arc, others linearly.
- ``pose_gap_ms`` is the distance from the frame time to the nearest sample. The pose is ``None``
  when that distance exceeds ``max_gap_ms``. Frame times outside the sample range are not
  extrapolated: within ``max_gap_ms`` of the first or last sample the pose holds that sample's
  value, further out it is ``None``. A long hole between two samples therefore gives ``None``
  in its middle, while the ends of the hole (within ``max_gap_ms`` of a sample) interpolate.

VERIFY: column names and units of the real pose log (FX-006); sign conventions (FX-006).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation, Slerp

from palmfx.offline.camera import LocalFrame

Pose = dict[str, float]
_CORE = ("lat_deg", "lon_deg", "alt_msl_m", "pitch_deg", "bank_deg")


def _heading_key(row: Mapping[str, Any]) -> str:
    return "heading_true_deg" if row.get("heading_true_deg") is not None else "heading_deg"


def _clean(
    rows: Sequence[Mapping[str, Any]], conventions: Mapping[str, float]
) -> list[dict[str, float]]:
    """Sort, de-duplicate and canonicalise sample rows (conventions applied, ``t`` in ns)."""
    out: list[dict[str, float]] = []
    for row in rows:
        try:
            vals = {k: float(row[k]) for k in _CORE}
            vals["heading_deg"] = float(row[_heading_key(row)])
            vals["t_ns"] = float(row["t_host_ns"])
        except (KeyError, TypeError, ValueError):
            continue
        if not all(math.isfinite(v) for v in vals.values()):
            continue
        vals["heading_deg"] *= float(conventions.get("heading_sign", 1))
        vals["pitch_deg"] *= float(conventions.get("pitch_sign", 1))
        vals["bank_deg"] *= float(conventions.get("bank_sign", 1))
        for k, v in row.items():
            if k.startswith("cam_") and v is not None:
                try:
                    f = float(v)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(f):
                    vals[k] = f
        out.append(vals)
    out.sort(key=lambda r: r["t_ns"])  # stable: input order breaks ties
    dedup: list[dict[str, float]] = []
    for r in out:
        if not dedup or r["t_ns"] != dedup[-1]["t_ns"]:
            dedup.append(r)
    # cam_* columns must exist on every kept row to be interpolated.
    if dedup:
        common = set.intersection(*(set(r) for r in dedup))
        dedup = [
            {k: v for k, v in r.items() if k in common or not k.startswith("cam_")} for r in dedup
        ]
    return dedup


def _wrap360(deg: float) -> float:
    out = float(deg % 360.0)
    return 0.0 if out >= 360.0 else out


def _arc_interp(a: float, b: float, w: float) -> float:
    delta = (b - a + 180.0) % 360.0 - 180.0
    return a + w * delta


def interpolate_poses_with_gap(
    rows: Sequence[Mapping[str, Any]],
    t_ns: Sequence[int] | NDArray[Any],
    max_gap_ms: float = 50,
    conventions: Mapping[str, float] | None = None,
) -> list[tuple[Pose | None, float | None]]:
    """Per frame time: ``(pose or None, pose_gap_ms)``. ``pose_gap_ms`` is None with no samples."""
    samples = _clean(rows, conventions or {})
    times = np.asarray(t_ns, dtype=np.float64).ravel()
    if not samples:
        return [(None, None) for _ in times]

    ts = np.array([s["t_ns"] for s in samples])
    frame = LocalFrame(samples[0]["lat_deg"], samples[0]["lon_deg"], samples[0]["alt_msl_m"])
    enu = frame.to_enu(
        [s["lat_deg"] for s in samples],
        [s["lon_deg"] for s in samples],
        [s["alt_msl_m"] for s in samples],
    )
    rot = Rotation.from_euler(
        "ZYX", [[s["heading_deg"], s["pitch_deg"], s["bank_deg"]] for s in samples], degrees=True
    )
    slerp = Slerp(ts, rot) if len(samples) > 1 else None
    cam_keys = sorted(k for k in samples[0] if k.startswith("cam_"))

    result: list[tuple[Pose | None, float | None]] = []
    for t in times:
        j = int(np.searchsorted(ts, t, side="left"))  # first sample >= t
        lo, hi = max(j - 1, 0), min(j, len(ts) - 1)
        gap_ms = float(min(abs(t - ts[lo]), abs(ts[hi] - t)) / 1e6)
        if gap_ms > max_gap_ms:
            result.append((None, gap_ms))
            continue
        if lo == hi or t <= ts[0] or t >= ts[-1]:
            i = 0 if t <= ts[0] else len(ts) - 1
            lo = hi = i
            w = 0.0
        else:
            w = float((t - ts[lo]) / (ts[hi] - ts[lo]))
        if lo == hi:
            p_enu = enu[lo]
            r_i = rot[lo]
        else:
            p_enu = (1.0 - w) * enu[lo] + w * enu[hi]
            assert slerp is not None
            r_i = slerp([t])[0]
        lat, lon, alt = frame.from_enu(p_enu)
        h, p, b = r_i.as_euler("ZYX", degrees=True)
        pose: Pose = {
            "lat_deg": float(lat[0]),
            "lon_deg": float(lon[0]),
            "alt_msl_m": float(alt[0]),
            "heading_deg": _wrap360(float(h)),
            "pitch_deg": float(p),
            "bank_deg": float(b),
        }
        for k in cam_keys:
            a, c = samples[lo][k], samples[hi][k]
            pose[k] = _arc_interp(a, c, w) if k.endswith("_deg") else (1.0 - w) * a + w * c
        result.append((pose, gap_ms))
    return result


def interpolate_poses(
    rows: Sequence[Mapping[str, Any]],
    t_ns: Sequence[int] | NDArray[Any],
    max_gap_ms: float = 50,
    conventions: Mapping[str, float] | None = None,
) -> list[Pose | None]:
    """Canonical pose at each time in ``t_ns`` (host ns), or None beyond ``max_gap_ms``."""
    return [p for p, _ in interpolate_poses_with_gap(rows, t_ns, max_gap_ms, conventions)]
