"""Canopy height model: DTM, DSM, CHM and smoothed CHM rasters from classified LiDAR points.

Input is a structured numpy array with fields ``X Y Z Classification ReturnNumber
NumberOfReturns`` in a local metric CRS (see ``palmscan.geo.local_crs``). The module is pure
numpy/scipy; ``rasterio`` is imported only by :func:`write_debug_rasters`.

Determinism: the grid origin is snapped to multiples of ``res`` (anchored at 0, 0 of the CRS),
cells are half-open ``[x0 + c*res, x0 + (c+1)*res)``, row 0 is the northern edge, and every
reduction is order independent (mean, max), so shuffling the input points gives the same rasters
up to float rounding of the ground mean. Ties for the cell maximum count as a building when any
tied return is class 6.

Classification codes are the ASPRS LAS 1.4 standard values: 1 unclassified, 2 ground, 6 building,
7 low point (noise), 18 high noise (ASPRS LAS specification, read 2026-11-22).
VERIFY: that the 3DEP EPT datasets used for San Diego and LA carry classes 2 and 6 as above, and
that Z is metres in one vertical datum after the SCAN-021 reprojection step. This module assumes
Z is metres and that DSM and DTM share one datum, so the CHM is a plain difference.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import numpy as np
import pyproj
from affine import Affine
from numpy.typing import NDArray
from scipy import ndimage
from scipy.spatial import Delaunay

from palmcore.errors import SourceError
from palmcore.log import get_logger

__all__ = ["ChmResult", "build_chm", "grid_for_bounds", "sample_ground", "write_debug_rasters"]

log = get_logger(__name__)

CLASS_GROUND: Final = 2
CLASS_BUILDING: Final = 6
NOISE_CLASSES: Final = (7, 18)
MAX_HEIGHT_M: Final = 60.0
_QUERY_OFFSET: Final = np.array([1.3e-2, 0.7e-2])

FloatArray = NDArray[np.float32]


@dataclass(slots=True)
class ChmResult:
    dtm: FloatArray  # metres, no NaN
    dsm: FloatArray  # metres, no NaN
    chm: FloatArray  # DSM - DTM, unsmoothed, in [0, 60]
    chm_smooth: FloatArray  # gaussian, sigma = smooth_sigma_px
    building_mask: NDArray[np.bool_] | None  # cells whose top first return is class 6
    transform: Affine  # north-up, row 0 = northern edge
    crs: pyproj.CRS
    res: float
    outliers: int = 0  # cells whose CHM exceeded 60 m and were zeroed


def grid_for_bounds(bounds: Sequence[float], res: float) -> tuple[Affine, int, int]:
    """Snap ``bounds`` (xmin, ymin, xmax, ymax) outward to multiples of ``res``.

    Returns ``(transform, height, width)``.
    """
    if res <= 0:
        raise ValueError("res must be positive")
    xmin, ymin, xmax, ymax = (float(v) for v in bounds)
    if not (xmax > xmin and ymax > ymin):
        raise ValueError(f"empty bounds: {tuple(bounds)}")
    x0 = math.floor(xmin / res) * res
    y0 = math.floor(ymin / res) * res
    y1 = math.ceil(ymax / res) * res
    width = max(1, round((math.ceil(xmax / res) * res - x0) / res))
    height = max(1, round((y1 - y0) / res))
    return Affine(res, 0.0, x0, 0.0, -res, y1), height, width


def _fill_nearest(values: NDArray[np.float64], valid: NDArray[np.bool_]) -> NDArray[np.float64]:
    idx = ndimage.distance_transform_edt(~valid, return_distances=False, return_indices=True)
    filled: NDArray[np.float64] = values[idx[0], idx[1]]
    return filled


def _linear_fill(
    values: NDArray[np.float64],
    known: NDArray[np.bool_],
    holes: NDArray[np.bool_],
    out: NDArray[np.float64],
) -> None:
    """Write linear-interpolated values for ``holes`` into ``out`` (NaN where outside the hull)."""
    kr, kc = np.nonzero(known)
    if kr.size < 3 or not holes.any():
        return
    hr, hc = np.nonzero(holes)
    try:
        tri = Delaunay(np.column_stack((kr, kc)).astype(np.float64))
        # Hole centres are lattice points like the vertices; a fixed sub-pixel offset (about
        # 0.01 px) keeps them off vertices and edges and the result deterministic.
        query = np.column_stack((hr, hc)).astype(np.float64) + _QUERY_OFFSET
        simplex = tri.find_simplex(query)
        ok = simplex >= 0
        t = tri.transform[simplex[ok]]
        b01 = np.einsum("nij,nj->ni", t[:, :2, :], query[ok] - t[:, 2, :])
        bary = np.column_stack((b01, 1.0 - b01.sum(axis=1)))
        verts = tri.simplices[simplex[ok]]
        vals = values[kr[verts], kc[verts]]
        res = np.full(hr.shape, np.nan)
        res[ok] = (bary * vals).sum(axis=1)
        out[hr, hc] = res
    except Exception:
        log.debug("linear DTM fill failed for a block")


def _fill_dtm(ground: NDArray[np.float64], valid: NDArray[np.bool_]) -> NDArray[np.float64]:
    """Fill empty DTM cells: linear in the hull of ground cells, nearest outside it.

    Triangulating every ground cell of a large tile is slow, so only the known cells that touch
    an empty cell (3x3 neighbourhood) are triangulated. Every triangle covering a gap has its
    vertices on the gap boundary, so the interpolated values are the same as with all cells.
    """
    if valid.all():
        return ground
    holes = ~valid
    band = ndimage.binary_dilation(holes, structure=np.ones((3, 3), dtype=bool)) & valid
    out = np.where(valid, ground, np.nan)
    _linear_fill(ground, band, holes, out)
    known = ~np.isnan(out)
    if not known.all():
        out = np.where(known, out, _fill_nearest(np.where(known, out, 0.0), known))
    return out


def build_chm(
    points: np.ndarray,
    bounds: Sequence[float],
    crs: pyproj.CRS | str,
    res: float = 0.5,
    smooth_sigma_px: float = 1.0,
    use_building_class: bool = True,
) -> ChmResult:
    """Rasterize DTM (class 2 mean), DSM (first-return max) and CHM = DSM - DTM at ``res`` metres.

    ``bounds`` is ``(xmin, ymin, xmax, ymax)`` in the CRS of ``points``. Points outside the snapped
    grid are dropped. Raises :class:`SourceError` when no ground points fall inside the grid.
    """
    transform, height, width = grid_for_bounds(bounds, res)
    x0, y1 = transform.c, transform.f
    x = np.asarray(points["X"], dtype=np.float64)
    y = np.asarray(points["Y"], dtype=np.float64)
    z = np.asarray(points["Z"], dtype=np.float64)
    cls = np.asarray(points["Classification"])
    ret = np.asarray(points["ReturnNumber"])

    col = np.floor((x - x0) / res).astype(np.int64)
    row = np.floor((y1 - y) / res).astype(np.int64)
    inside = (col >= 0) & (col < width) & (row >= 0) & (row < height) & np.isfinite(z)
    flat = row * width + col
    n_cells = height * width

    # DTM: per-cell mean of class 2.
    g = inside & (cls == CLASS_GROUND)
    if not g.any():
        raise SourceError("no ground points")
    gsum = np.bincount(flat[g], weights=z[g], minlength=n_cells)
    gcnt = np.bincount(flat[g], minlength=n_cells)
    gvalid = (gcnt > 0).reshape(height, width)
    ground = np.where(gvalid, (gsum / np.maximum(gcnt, 1)).reshape(height, width), np.nan)
    dtm = _fill_dtm(ground, gvalid)

    # DSM: per-cell max of first returns (noise classes excluded).
    f = inside & (ret == 1) & ~np.isin(cls, NOISE_CLASSES)
    dsm_flat = np.full(n_cells, -np.inf)
    np.maximum.at(dsm_flat, flat[f], z[f])
    dsm = dsm_flat.reshape(height, width)
    top_valid = np.isfinite(dsm)

    building: NDArray[np.bool_] | None = None
    if use_building_class and bool((cls[inside] == CLASS_BUILDING).any()):
        tied = f & (cls == CLASS_BUILDING) & (z == dsm_flat[flat])
        building = np.bincount(flat[tied], minlength=n_cells).reshape(height, width) > 0

    # Outliers (birds, wires, noise): counted on cells that have a first return, set to the
    # ground so they do not spread through the hole fill below.
    tall = top_valid & (np.where(top_valid, dsm, 0.0) - dtm > MAX_HEIGHT_M)
    outliers = int(tall.sum())
    if outliers:
        dsm = np.where(tall, dtm, dsm)
        log.warning("zeroed %d CHM cells above %.0f m", outliers, MAX_HEIGHT_M)

    # One 3x3 max-filter pass closes single-cell holes; the rest falls back to the DTM.
    if not top_valid.all():
        grown = ndimage.maximum_filter(dsm, size=3, mode="nearest")
        dsm = np.where(top_valid, dsm, grown)
    dsm = np.where(np.isfinite(dsm), dsm, dtm)

    chm = dsm - dtm
    chm[chm < 0] = 0.0

    chm32 = chm.astype(np.float32)
    smooth = (
        ndimage.gaussian_filter(chm32, sigma=smooth_sigma_px)
        if smooth_sigma_px > 0
        else chm32.copy()
    )
    return ChmResult(
        dtm=dtm.astype(np.float32),
        dsm=dsm.astype(np.float32),
        chm=chm32,
        chm_smooth=smooth.astype(np.float32),
        building_mask=building,
        transform=transform,
        crs=pyproj.CRS.from_user_input(crs),
        res=float(res),
        outliers=outliers,
    )


def sample_ground(chm: ChmResult, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Bilinear DTM elevation at ``x, y`` (CRS of the result). NaN outside the raster extent."""
    xs = np.asarray(x, dtype=np.float64)
    ys = np.asarray(y, dtype=np.float64)
    height, width = chm.dtm.shape
    t = chm.transform
    fc = (xs - t.c) / chm.res - 0.5  # fractional cell-centre coordinates
    fr = (t.f - ys) / chm.res - 0.5
    outside = ~((fc >= -0.5) & (fc <= width - 0.5) & (fr >= -0.5) & (fr <= height - 0.5))
    fc = np.clip(np.nan_to_num(fc), 0.0, width - 1.0)
    fr = np.clip(np.nan_to_num(fr), 0.0, height - 1.0)
    c0 = np.minimum(np.floor(fc).astype(np.int64), max(width - 2, 0))
    r0 = np.minimum(np.floor(fr).astype(np.int64), max(height - 2, 0))
    c1 = np.minimum(c0 + 1, width - 1)
    r1 = np.minimum(r0 + 1, height - 1)
    wc = fc - c0
    wr = fr - r0
    d = chm.dtm.astype(np.float64)
    out: NDArray[np.float64] = (
        d[r0, c0] * (1 - wc) * (1 - wr)
        + d[r0, c1] * wc * (1 - wr)
        + d[r1, c0] * (1 - wc) * wr
        + d[r1, c1] * wc * wr
    )
    out[outside] = np.nan
    return out


def write_debug_rasters(chm: ChmResult, out_dir: Path) -> None:
    """Write dtm, dsm, chm, chm_smooth (float32) and building_mask (uint8) as GeoTIFFs."""
    import rasterio  # imported here so the module works without rasterio

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    layers: dict[str, np.ndarray] = {
        "dtm": chm.dtm,
        "dsm": chm.dsm,
        "chm": chm.chm,
        "chm_smooth": chm.chm_smooth,
    }
    if chm.building_mask is not None:
        layers["building_mask"] = chm.building_mask.astype(np.uint8)
    for name, arr in layers.items():
        with rasterio.open(
            out_dir / f"{name}.tif",
            "w",
            driver="GTiff",
            height=arr.shape[0],
            width=arr.shape[1],
            count=1,
            dtype=arr.dtype,
            crs=chm.crs,
            transform=chm.transform,
            compress="deflate",
        ) as dst:
            dst.write(arr, 1)
