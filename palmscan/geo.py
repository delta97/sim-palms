"""Local metric CRS helpers for palmscan: thin wrappers over ``palmcore.geo``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pyproj
from numpy.typing import ArrayLike

from palmcore import geo as _geo
from palmcore.geo import WGS84, Bbox

__all__ = ["WGS84", "Bbox", "local_crs", "to_local", "to_wgs84"]

CrsLike = str | pyproj.CRS


def local_crs(bbox: Bbox | Sequence[float], override: str | None = None) -> pyproj.CRS:
    """Metric CRS for work inside ``bbox``: the UTM zone of its centre (or ``override``).

    ``bbox`` is a :class:`palmcore.geo.Bbox` or ``[lon_min, lat_min, lon_max, lat_max]``.
    A San Diego bbox gives EPSG:32611.
    """
    box = bbox if isinstance(bbox, Bbox) else Bbox.from_list(bbox)
    return pyproj.CRS.from_user_input(_geo.local_crs_for(box, override))


def _crs_text(crs: CrsLike) -> str:
    if isinstance(crs, pyproj.CRS):
        authority = crs.to_authority()
        return f"{authority[0]}:{authority[1]}" if authority else crs.to_wkt()
    return crs


def _apply(src: str, dst: str, a: ArrayLike, b: ArrayLike) -> tuple[Any, Any]:
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    out_a, out_b = _geo.transformer(src, dst).transform(arr_a, arr_b)
    if arr_a.ndim == 0:
        return float(out_a), float(out_b)
    return np.asarray(out_a, dtype=float), np.asarray(out_b, dtype=float)


def to_local(lon: ArrayLike, lat: ArrayLike, crs: CrsLike) -> tuple[Any, Any]:
    """WGS84 lon/lat (scalars or numpy arrays) to ``crs`` x/y, same shape as the input."""
    return _apply(WGS84, _crs_text(crs), lon, lat)


def to_wgs84(x: ArrayLike, y: ArrayLike, crs: CrsLike) -> tuple[Any, Any]:
    """``crs`` x/y (scalars or numpy arrays) to WGS84 lon/lat, same shape as the input."""
    return _apply(_crs_text(crs), WGS84, x, y)
