"""palmfx.offline.depth: log24 depth packing and the depth model.

Usage note (shader side, untested until FX-007):
1. Copy palmfx/offline/capture/PalmFxDepthPack.fx into ReShade's reshade-shaders/Shaders folder.
2. In the ReShade overlay, enable PalmFxDepthPack and disable every other effect.
3. Set the depth preprocessor flags found in FX-001 and record them in session.json.
4. Save screenshots before and after effects; the "after" PNG holds the packed depth.
5. Decode with read_depth_png (RGB order) or unpack_log24.
6. Fit z = a / (d + b) with fit_depth_model once ground-truth ranges exist (FX-009).

pack_log24 mirrors PalmFxDepthPack.fx: same DMIN, same rounding (floor(x + 0.5)).
The shader works in float32 and this module in float64, so a rare value may differ by one
code (about 1e-6 relative); the decode error bound is half a code, about 5e-7 relative.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from palmcore.errors import ConfigError
from palmfx.offline.session import read_image

DMIN = 1e-7
VMAX = 16777215  # 2**24 - 1


def pack_log24(d: NDArray[Any], dmin: float = DMIN) -> NDArray[np.uint8]:
    """Pack raw depth into an (..., 3) uint8 RGB array. d < dmin (and NaN) packs to 0."""
    arr = np.asarray(d, dtype=np.float64)
    valid = np.isfinite(arr) & (arr >= dmin)
    safe = np.where(valid, arr, dmin)
    t = (np.log(safe) - np.log(dmin)) / (-np.log(dmin))
    v = np.where(valid, np.floor(np.clip(t, 0.0, 1.0) * VMAX + 0.5), 0.0)
    r = np.floor(v / 65536.0)
    g = np.floor(np.fmod(v, 65536.0) / 256.0)
    b = np.fmod(v, 256.0)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


def unpack_log24(rgb: NDArray[Any], dmin: float = DMIN) -> NDArray[np.float64]:
    """Inverse of pack_log24. Code 0 decodes to 0.0 (sky or below dmin)."""
    a = np.asarray(rgb)
    if a.ndim < 1 or a.shape[-1] < 3:
        raise ConfigError("unpack_log24 needs an array with at least 3 channels")
    a = a[..., :3].astype(np.float64)
    v = a[..., 0] * 65536.0 + a[..., 1] * 256.0 + a[..., 2]
    d = np.exp(np.log(dmin) + v / VMAX * (-np.log(dmin)))
    return np.where(v == 0, 0.0, d)


def read_depth_png(path: Path) -> NDArray[np.float64]:
    """Read a packed-depth PNG (RGB order, alpha ignored) and return raw depth d."""
    img = read_image(path)
    if img.dtype != np.uint8 or img.ndim != 3:
        raise ConfigError(f"{path}: expected an 8-bit colour PNG")
    return unpack_log24(img)


@dataclass(frozen=True)
class DepthModel:
    """z = a / (d + b), metres from raw depth. rms_rel is the fit's RMS relative error."""

    a: float
    b: float
    rms_rel: float = 0.0


def fit_depth_model(d: NDArray[Any], z: NDArray[Any]) -> DepthModel:
    """Least squares of 1/z = d/a + b/a (linear in d). Pairs with d <= 0 or z <= 0 are skipped."""
    dd = np.asarray(d, dtype=np.float64).ravel()
    zz = np.asarray(z, dtype=np.float64).ravel()
    if dd.shape != zz.shape:
        raise ConfigError("fit_depth_model: d and z must have the same size")
    ok = np.isfinite(dd) & np.isfinite(zz) & (dd > 0) & (zz > 0)
    if int(ok.sum()) < 2 or np.ptp(dd[ok]) == 0:
        raise ConfigError("fit_depth_model: need at least 2 distinct valid (d, z) pairs")
    dd, zz = dd[ok], zz[ok]
    slope, icpt = np.polyfit(dd, 1.0 / zz, 1)
    if slope == 0:
        raise ConfigError("fit_depth_model: degenerate fit (zero slope)")
    a = 1.0 / slope
    b = icpt * a
    with np.errstate(divide="ignore", invalid="ignore"):
        pred = a / (dd + b)
        rel = (pred - zz) / zz
    rel = rel[np.isfinite(rel)]
    rms = float(np.sqrt(np.mean(rel**2))) if rel.size else float("nan")
    return DepthModel(a=float(a), b=float(b), rms_rel=rms)


def to_metric(d: NDArray[Any], model: DepthModel) -> NDArray[np.float64]:
    """Metres from raw depth. NaN where d == 0 (sky) or the model gives a non-positive z."""
    arr = np.asarray(d, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = model.a / (arr + model.b)
    return np.where((arr == 0) | ~np.isfinite(z) | (z <= 0), np.nan, z)
