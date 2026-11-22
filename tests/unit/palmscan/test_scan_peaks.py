"""Tests for palmscan.detect.peaks (SCAN-023) on synthetic canopy height rasters."""

from __future__ import annotations

import numpy as np
import pyproj
import pytest
from affine import Affine
from scipy import ndimage

from palmscan.detect.chm import ChmResult
from palmscan.detect.peaks import crown_stats, find_peaks, segment_crowns

CRS = "EPSG:32611"
RES = 0.5
X0, Y1 = 500000.0, 3600060.0
SIZE = 120  # 60 m x 60 m


def xy_to_rc(x: float, y: float) -> tuple[float, float]:
    return (Y1 - y) / RES - 0.5, (x - X0) / RES - 0.5


def dome(chm: np.ndarray, x: float, y: float, height: float, radius: float) -> np.ndarray:
    """Add a hemispherical-profile crown (steep sides) by taking the max with the surface."""
    rr, cc = np.mgrid[0:SIZE, 0:SIZE]
    r0, c0 = xy_to_rc(x, y)
    d = np.hypot(rr - r0, cc - c0) * RES
    inside = d < radius
    surf = np.where(inside, height * np.sqrt(np.clip(1 - (d / radius) ** 2, 0, 1)), 0.0)
    return np.maximum(chm, surf)


def make_chm(chm: np.ndarray, sigma: float = 1.0, building: np.ndarray | None = None) -> ChmResult:
    chm32 = chm.astype(np.float32)
    smooth = ndimage.gaussian_filter(chm32, sigma=sigma) if sigma > 0 else chm32.copy()
    dtm = np.full(chm32.shape, 100.0, dtype=np.float32)
    return ChmResult(
        dtm=dtm,
        dsm=dtm + chm32,
        chm=chm32,
        chm_smooth=smooth.astype(np.float32),
        building_mask=building,
        transform=Affine(RES, 0.0, X0, 0.0, -RES, Y1),
        crs=pyproj.CRS.from_user_input(CRS),
        res=RES,
    )


def run(chm: ChmResult, bounds: tuple[float, float, float, float] | None = None):  # type: ignore[no-untyped-def]
    peaks = find_peaks(chm)
    labels = segment_crowns(chm, peaks)
    return peaks, labels, crown_stats(chm, labels, peaks, "ds", "t1", bounds)


def test_two_separate_crowns() -> None:
    raw = np.zeros((SIZE, SIZE))
    raw = dome(raw, X0 + 15, Y1 - 30, 15.0, 3.0)  # diameter 6
    raw = dome(raw, X0 + 40, Y1 - 30, 12.0, 4.0)  # diameter 8
    peaks, labels, cands = run(make_chm(raw))
    assert len(peaks) == 2 and len(cands) == 2
    assert sorted(int(v) for v in np.unique(labels)) == [0, 1, 2]
    a, b = cands
    assert a.height_m == pytest.approx(15.0, abs=0.5)
    assert b.height_m == pytest.approx(12.0, abs=0.5)
    assert a.crown_diam_m == pytest.approx(6.0, abs=0.5)
    assert b.crown_diam_m == pytest.approx(8.0, abs=0.5)
    assert a.ratio == pytest.approx(a.height_m / a.crown_diam_m)
    assert a.x == pytest.approx(X0 + 15, abs=RES) and a.y == pytest.approx(Y1 - 30, abs=RES)
    assert a.ground_elev_m == pytest.approx(100.0)
    assert -117.1 < a.lon < -116.9 and 32.4 < a.lat < 32.7  # UTM 11 near San Diego
    assert a.shared_boundary_frac < 0.1 and b.shared_boundary_frac < 0.1
    assert not a.in_building


def test_close_crowns_give_one_peak() -> None:
    raw = np.zeros((SIZE, SIZE))
    raw = dome(raw, X0 + 30, Y1 - 30, 14.0, 3.0)
    raw = dome(raw, X0 + 32, Y1 - 30, 14.0, 3.0)
    assert len(find_peaks(make_chm(raw))) == 1


def test_peaks_below_min_height_ignored() -> None:
    raw = dome(np.zeros((SIZE, SIZE)), X0 + 30, Y1 - 30, 5.0, 3.0)
    peaks = find_peaks(make_chm(raw))
    assert peaks.shape == (0, 2)
    chm = make_chm(raw)
    assert crown_stats(chm, segment_crowns(chm, peaks), peaks, "ds", "t1") == []


def test_cone_embedded_in_canopy_is_not_isolated() -> None:
    """A tall crown ringed by 8 m crowns (a plateau of lower canopy) vs an isolated crown."""
    raw = np.zeros((SIZE, SIZE))
    cx, cy = X0 + 30, Y1 - 30
    for k in range(6):
        ang = k * np.pi / 3
        raw = dome(raw, cx + 6.5 * np.cos(ang), cy + 6.5 * np.sin(ang), 8.0, 4.0)
    raw = dome(raw, cx, cy, 16.0, 3.5)
    _p, _l, cands = run(make_chm(raw))
    assert len(cands) == 7
    centre = min(cands, key=lambda c: abs(c.x - cx) + abs(c.y - cy))
    assert centre.height_m == pytest.approx(16.0, abs=0.5)
    assert centre.shared_boundary_frac > 0.5

    alone = dome(np.zeros((SIZE, SIZE)), cx, cy, 16.0, 3.5)
    _p, _l, solo = run(make_chm(alone))
    assert len(solo) == 1 and solo[0].shared_boundary_frac < 0.1


def test_wide_plateau_is_a_single_extra_peak() -> None:
    raw = np.zeros((SIZE, SIZE))
    raw[20:100, 20:100] = 8.0
    raw = dome(raw, X0 + 30, Y1 - 30, 16.0, 3.0)
    peaks = find_peaks(make_chm(raw))
    assert len(peaks) == 2  # the flat top is one peak, not one per cell


def test_plateau_top_is_one_peak_with_first_cell_tiebreak() -> None:
    raw = np.zeros((SIZE, SIZE))
    raw[40:60, 40:60] = 10.0
    chm = make_chm(raw, sigma=0)
    peaks = find_peaks(chm)
    assert peaks.tolist() == [[40, 40]]


def test_noise_does_not_create_peaks_after_smoothing() -> None:
    rng = np.random.default_rng(7)
    raw = rng.uniform(0.0, 0.3, (SIZE, SIZE))
    assert len(find_peaks(make_chm(raw))) == 0


def test_buffer_peak_dropped() -> None:
    raw = np.zeros((SIZE, SIZE))
    raw = dome(raw, X0 + 8, Y1 - 30, 15.0, 3.0)  # inside the 10 m buffer strip
    raw = dome(raw, X0 + 40, Y1 - 30, 15.0, 3.0)
    bounds = (X0 + 10, Y1 - 50, X0 + 50, Y1 - 10)
    _p, _l, cands = run(make_chm(raw), bounds)
    assert len(cands) == 1
    assert cands[0].x == pytest.approx(X0 + 40, abs=RES)
    _p, _l, all_cands = run(make_chm(raw))
    assert len(all_cands) == 2


def test_ids_deterministic_and_stable() -> None:
    raw = np.zeros((SIZE, SIZE))
    raw = dome(raw, X0 + 40, Y1 - 30, 15.0, 3.0)
    raw = dome(raw, X0 + 15, Y1 - 30, 15.0, 3.0)
    chm = make_chm(raw)
    _p, l1, c1 = run(chm)
    _p, l2, c2 = run(chm)
    assert np.array_equal(l1, l2)
    assert [c.candidate_id for c in c1] == [c.candidate_id for c in c2]
    # Peaks sorted by (row, col): same row, so the western crown is label 1.
    assert [c.candidate_id for c in c1] == ["ds:t1:1", "ds:t1:2"]
    assert c1[0].x < c1[1].x


def test_in_building_from_mask() -> None:
    raw = dome(np.zeros((SIZE, SIZE)), X0 + 30, Y1 - 30, 12.0, 3.0)
    mask = np.zeros((SIZE, SIZE), dtype=bool)
    mask[50:70, 50:70] = True
    _p, _l, cands = run(make_chm(raw, building=mask))
    assert len(cands) == 1 and cands[0].in_building


def test_height_uses_unsmoothed_chm() -> None:
    raw = np.zeros((SIZE, SIZE))
    r, c = 60, 60
    raw[r - 3 : r + 4, c - 3 : c + 4] = 10.0
    raw[r, c] = 13.0  # single-cell spike
    chm = make_chm(raw)
    _p, _l, cands = run(chm)
    assert cands[0].height_m == pytest.approx(13.0)
    assert chm.chm_smooth.max() < 13.0
