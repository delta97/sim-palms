"""Treetop detection and watershed crown segmentation on the canopy height model.

Detection and the watershed use the smoothed CHM; crown height uses the unsmoothed CHM.

Determinism: peaks are returned sorted by (row, col); a flat-topped crown (equal smoothed values)
yields one peak, the first of its plateau in row-major order; labels are ``index + 1`` in peak
order, and candidate ids use that label number, so an id does not depend on which other peaks are
dropped.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray
from scipy import ndimage
from skimage.segmentation import watershed

from palmscan.detect.chm import ChmResult, sample_ground
from palmscan.geo import to_wgs84
from palmscan.model import LidarCandidate

__all__ = ["crown_stats", "find_peaks", "segment_crowns"]

_EIGHT = np.ones((3, 3), dtype=bool)
_TOL = 1e-4  # metres; float32 noise on flat tops


def find_peaks(
    chm: ChmResult, min_height_m: float = 6.0, min_distance_m: float = 3.0
) -> NDArray[np.int64]:
    """Local maxima of the smoothed CHM as an ``(n, 2)`` array of (row, col), sorted.

    A maximum must reach ``min_height_m`` and be the highest cell within ``min_distance_m``.
    Connected cells with equal values (a plateau) count as one peak.
    """
    smooth = chm.chm_smooth
    distance_px = max(1, round(min_distance_m / chm.res))
    # Cells that equal the maximum of their 3x3 neighbourhood (within float noise): adjacent
    # such cells form a plateau, because two neighbouring maxima must have equal values.
    local_max = (smooth >= ndimage.maximum_filter(smooth, size=3) - _TOL) & (smooth >= min_height_m)
    comp, n = ndimage.label(local_max, structure=_EIGHT)
    if n == 0:
        return np.empty((0, 2), dtype=np.int64)
    top = np.asarray(ndimage.maximum(smooth, comp, np.arange(1, n + 1)), dtype=np.float64)
    rows, cols = np.nonzero(comp)  # row-major
    ids = comp[rows, cols]
    at_top = smooth[rows, cols] >= top[ids - 1] - _TOL
    rows, cols, ids = rows[at_top], cols[at_top], ids[at_top]
    _, first = np.unique(ids, return_index=True)  # first cell of each plateau, row-major
    rows, cols = rows[first], cols[first]
    values = smooth[rows, cols]
    # Highest first, ties by (row, col); a peak suppresses lower ones within min_distance.
    order = np.lexsort((cols, rows, -values))
    height, width = smooth.shape
    suppressed = np.zeros(smooth.shape, dtype=bool)
    kept: list[tuple[int, int]] = []
    for i in order:
        r, c = int(rows[i]), int(cols[i])
        if suppressed[r, c]:
            continue
        kept.append((r, c))
        suppressed[
            max(r - distance_px, 0) : min(r + distance_px + 1, height),
            max(c - distance_px, 0) : min(c + distance_px + 1, width),
        ] = True
    return np.array(sorted(kept), dtype=np.int64).reshape(-1, 2)


def segment_crowns(
    chm: ChmResult, peaks: np.ndarray, mask_height_m: float = 2.0
) -> NDArray[np.int32]:
    """Watershed labels (0 = background); peak ``i`` gets label ``i + 1``."""
    smooth = chm.chm_smooth
    labels = np.zeros(smooth.shape, dtype=np.int32)
    if len(peaks) == 0:
        return labels
    markers = np.zeros(smooth.shape, dtype=np.int32)
    markers[peaks[:, 0], peaks[:, 1]] = np.arange(1, len(peaks) + 1, dtype=np.int32)
    flooded = watershed(  # type: ignore[no-untyped-call]
        -smooth, markers, mask=smooth > mask_height_m
    )
    out: NDArray[np.int32] = np.asarray(flooded).astype(np.int32)
    return out


def _boundary_counts(labels: NDArray[np.int32], n: int) -> tuple[np.ndarray, np.ndarray]:
    """Per label: boundary pixel count and boundary pixels touching another label (4-neighbours)."""
    padded = np.pad(labels, 1, mode="constant")
    centre = padded[1:-1, 1:-1]
    is_bnd = np.zeros(labels.shape, dtype=bool)
    shared = np.zeros(labels.shape, dtype=bool)
    for nb in (padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]):
        diff = nb != centre
        is_bnd |= diff
        shared |= diff & (nb > 0)
    fg = centre > 0
    total = np.bincount(centre[is_bnd & fg], minlength=n + 1)
    touching = np.bincount(centre[shared & fg], minlength=n + 1)
    return total, touching


def crown_stats(
    chm: ChmResult,
    labels: np.ndarray,
    peaks: np.ndarray,
    dataset: str,
    tile_id: str,
    tile_bounds: Sequence[float] | None = None,
) -> list[LidarCandidate]:
    """One :class:`LidarCandidate` per crown label, in label order.

    ``tile_bounds`` (xmin, ymin, xmax, ymax, local CRS, without buffer) drops candidates whose
    peak lies outside it, so neighbouring tiles do not double-count; ``None`` keeps all.
    ``shared_boundary_frac`` is the share of a crown's boundary pixels (4-neighbour outside the
    crown) that touch another crown: 0 isolated, 1 fully embedded in canopy.
    """
    n = len(peaks)
    if n == 0:
        return []
    res = chm.res
    index = np.arange(1, n + 1)
    counts = np.bincount(labels.ravel(), minlength=n + 1)
    heights = np.asarray(ndimage.maximum(chm.chm, labels, index), dtype=np.float64)
    bnd_total, bnd_shared = _boundary_counts(labels, n)

    rows, cols = peaks[:, 0], peaks[:, 1]
    t = chm.transform
    xs = t.c + (cols + 0.5) * t.a
    ys = t.f + (rows + 0.5) * t.e
    lons, lats = to_wgs84(xs, ys, chm.crs)
    ground = sample_ground(chm, xs, ys)

    keep = np.ones(n, dtype=bool)
    if tile_bounds is not None:
        xmin, ymin, xmax, ymax = (float(v) for v in tile_bounds)
        keep = (xs >= xmin) & (xs < xmax) & (ys >= ymin) & (ys < ymax)

    out: list[LidarCandidate] = []
    for i in range(n):
        label = i + 1
        count = int(counts[label])
        if count == 0 or not keep[i]:
            continue
        area = count * res * res
        diam = 2.0 * math.sqrt(area / math.pi)
        height = float(heights[i])
        total = int(bnd_total[label])
        g = float(ground[i])
        out.append(
            LidarCandidate(
                candidate_id=f"{dataset}:{tile_id}:{label}",
                dataset=dataset,
                x=float(xs[i]),
                y=float(ys[i]),
                lon=float(lons[i]),
                lat=float(lats[i]),
                height_m=height,
                crown_area_m2=area,
                crown_diam_m=diam,
                ratio=height / diam,
                shared_boundary_frac=float(bnd_shared[label]) / total if total else 0.0,
                ground_elev_m=None if math.isnan(g) else g,
                in_building=bool(
                    chm.building_mask is not None and chm.building_mask[rows[i], cols[i]]
                ),
            )
        )
    return out
