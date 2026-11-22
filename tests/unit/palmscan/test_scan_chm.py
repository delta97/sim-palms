"""Tests for palmscan.detect.chm (SCAN-022) on synthetic point clouds."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pytest

from palmcore.errors import SourceError
from palmscan.detect.chm import (
    ChmResult,
    build_chm,
    grid_for_bounds,
    sample_ground,
    write_debug_rasters,
)

CRS = "EPSG:32611"
DTYPE = np.dtype(
    [
        ("X", "f8"),
        ("Y", "f8"),
        ("Z", "f8"),
        ("Classification", "u1"),
        ("ReturnNumber", "u1"),
        ("NumberOfReturns", "u1"),
    ]
)
BOUNDS = (500000.0, 3600000.0, 500060.0, 3600060.0)


def make_points(
    bounds: tuple[float, float, float, float] = BOUNDS,
    density: float = 8.0,
    base: float = 10.0,
    slope: float = 0.0,
    cones: tuple[tuple[float, float, float, float], ...] = (),
    plateaus: tuple[tuple[float, float, float, float, int], ...] = (),
    poles: tuple[tuple[float, float, float], ...] = (),
    seed: int = 1,
) -> np.ndarray:
    """Ground (class 2) with slope along +X, cone trees (cx, cy, height, radius), plateaus
    (cx, cy, half_width, height, class) and poles (x, y, height; a thin vertical column)."""
    rng = np.random.default_rng(seed)
    xmin, ymin, xmax, ymax = bounds
    n = int((xmax - xmin) * (ymax - ymin) * density)
    x = rng.uniform(xmin, xmax, n)
    y = rng.uniform(ymin, ymax, n)
    ground_z = base + slope * (x - xmin)
    parts = [(x, y, ground_z, np.full(n, 2), np.ones(n))]
    # First returns over the same footprint (canopy-free first returns hit the ground).
    parts.append((x, y, ground_z + 0.01, np.full(n, 1), np.ones(n)))
    for cx, cy, h, r in cones:
        m = int(np.pi * r * r * density * 6)
        rr = r * np.sqrt(rng.uniform(0, 1, m))
        th = rng.uniform(0, 2 * np.pi, m)
        px, py = cx + rr * np.cos(th), cy + rr * np.sin(th)
        pz = base + slope * (px - xmin) + h * (1 - rr / r)
        parts.append((px, py, pz, np.full(m, 1), np.ones(m)))
        # Guarantee the apex is sampled.
        parts.append(
            (
                np.array([cx]),
                np.array([cy]),
                np.array([base + slope * (cx - xmin) + h]),
                np.array([1]),
                np.ones(1),
            )
        )
    for cx, cy, hw, h, k in plateaus:
        m = int(4 * hw * hw * density * 6)
        px = rng.uniform(cx - hw, cx + hw, m)
        py = rng.uniform(cy - hw, cy + hw, m)
        pz = np.full(m, base + h)
        parts.append((px, py, pz, np.full(m, k), np.ones(m)))
    for px0, py0, h in poles:
        m = 20
        parts.append(
            (
                np.full(m, px0),
                np.full(m, py0),
                base + slope * (px0 - xmin) + np.linspace(0.1, h, m),
                np.full(m, 1),
                np.ones(m),
            )
        )
    arr = np.concatenate(
        [np.rec.fromarrays([p[0], p[1], p[2], p[3], p[4], p[4]], dtype=DTYPE) for p in parts]
    )
    return np.asarray(arr)


def cell_of(res: ChmResult, x: float, y: float) -> tuple[int, int]:
    t = res.transform
    return int((t.f - y) // res.res), int((x - t.c) // res.res)


def test_grid_snapping() -> None:
    t, h, w = grid_for_bounds((500000.3, 3600000.1, 500010.2, 3600005.9), 0.5)
    assert (t.c, t.f) == (500000.0, 3600006.0)
    assert (h, w) == (12, 21)
    assert t.a == 0.5 and t.e == -0.5
    with pytest.raises(ValueError):
        grid_for_bounds((1, 1, 1, 2), 0.5)


def test_cone_peak_on_flat_ground() -> None:
    pts = make_points(cones=((500030.25, 3600030.25, 20.0, 2.0),))
    res = build_chm(pts, BOUNDS, CRS)
    r, c = cell_of(res, 500030.25, 3600030.25)
    assert abs(float(res.chm[r, c]) - 20.0) <= 0.5
    assert np.unravel_index(np.argmax(res.chm), res.chm.shape) == (r, c)
    assert float(res.chm[10:20, 10:20].max()) < 0.2  # far from the tree
    assert res.chm.dtype == np.float32 and not np.isnan(res.dtm).any()
    assert res.building_mask is None and res.outliers == 0
    assert res.chm_smooth.max() < res.chm.max()


def test_sloped_ground_gives_near_zero_chm() -> None:
    pts = make_points(slope=0.05, base=20.0)
    res = build_chm(pts, BOUNDS, CRS)
    assert float(np.percentile(res.chm, 99)) < 0.3


def test_sloped_ground_with_tree_keeps_height() -> None:
    pts = make_points(slope=0.05, cones=((500030.25, 3600030.25, 15.0, 2.0),))
    res = build_chm(pts, BOUNDS, CRS)
    r, c = cell_of(res, 500030.25, 3600030.25)
    assert abs(float(res.chm[r, c]) - 15.0) <= 0.8
    far = np.ones(res.chm.shape, bool)
    far[max(r - 12, 0) : r + 12, max(c - 12, 0) : c + 12] = False
    assert float(np.percentile(res.chm[far], 99)) < 0.3


def test_ground_gap_filled() -> None:
    pts = make_points(slope=0.02)
    gap = (
        (pts["Classification"] == 2) & (abs(pts["X"] - 500030) < 6) & (abs(pts["Y"] - 3600030) < 6)
    )
    pts = pts[~gap]
    res = build_chm(pts, BOUNDS, CRS)
    expected = 10.0 + 0.02 * (500030 - BOUNDS[0])
    got = sample_ground(res, np.array([500030.0]), np.array([3600030.0]))
    assert abs(got[0] - expected) < 0.1
    assert not np.isnan(res.dtm).any()
    assert float(res.chm.max()) < 0.3


def test_ground_edge_gap_uses_nearest() -> None:
    pts = make_points(slope=0.0)
    pts = pts[~((pts["Classification"] == 2) & (pts["X"] > 500050))]
    res = build_chm(pts, BOUNDS, CRS)
    assert not np.isnan(res.dtm).any()
    assert abs(float(res.dtm[30, -1]) - 10.0) < 0.05


def test_collinear_ground_falls_back_to_nearest() -> None:
    n = 50
    pts = np.zeros(n, dtype=DTYPE)
    pts["X"] = 500010.25
    pts["Y"] = np.linspace(3600001, 3600059, n)
    pts["Z"] = 7.0
    pts["Classification"] = 2
    pts["ReturnNumber"] = 1
    res = build_chm(pts, BOUNDS, CRS)
    assert np.allclose(res.dtm, 7.0)


def test_negative_chm_clipped() -> None:
    pts = make_points()
    # A first return 2 m below the ground (multipath-like) must not produce a negative CHM.
    low = np.zeros(1, dtype=DTYPE)
    low["X"], low["Y"], low["Z"] = 500020.25, 3600020.25, 5.0
    low["Classification"], low["ReturnNumber"] = 1, 1
    # Make the low point the only first return in its cell (ground stays class 2 elsewhere).
    near = (abs(pts["X"] - 500020.25) < 0.25) & (abs(pts["Y"] - 3600020.25) < 0.25)
    pts = np.concatenate([pts[~(near & (pts["ReturnNumber"] == 1))], low])
    res = build_chm(pts, BOUNDS, CRS)
    assert float(res.chm.min()) == 0.0
    assert (
        float(res.dsm[cell_of(res, 500020.25, 3600020.25)]) < 10.0
    )  # the raw DSM still shows the dip


def test_spike_removed_and_counted() -> None:
    pts = make_points()
    spike = np.zeros(1, dtype=DTYPE)
    spike["X"], spike["Y"], spike["Z"] = 500015.25, 3600015.25, 110.0
    spike["Classification"], spike["ReturnNumber"] = 1, 1
    res = build_chm(np.concatenate([pts, spike]), BOUNDS, CRS)
    r, c = cell_of(res, 500015.25, 3600015.25)
    assert res.outliers == 1
    assert float(res.chm[r, c]) == 0.0
    assert float(res.dsm[r, c]) == pytest.approx(float(res.dtm[r, c]))
    assert float(res.chm.max()) <= 60.0


def test_noise_class_not_used_in_dsm() -> None:
    pts = make_points()
    noise = np.zeros(1, dtype=DTYPE)
    noise["X"], noise["Y"], noise["Z"] = 500015.25, 3600015.25, 40.0
    noise["Classification"], noise["ReturnNumber"] = 18, 1
    res = build_chm(np.concatenate([pts, noise]), BOUNDS, CRS)
    assert float(res.chm.max()) < 0.2 and res.outliers == 0


def test_single_cell_dsm_hole_filled_by_neighbours() -> None:
    pts = make_points(plateaus=((500030.0, 3600030.0, 5.0, 8.0, 1),))
    hole = (abs(pts["X"] - 500030.25) < 0.25) & (abs(pts["Y"] - 3600030.25) < 0.25)
    pts = pts[~(hole & (pts["ReturnNumber"] == 1))]
    res = build_chm(pts, BOUNDS, CRS)
    r, c = cell_of(res, 500030.25, 3600030.25)
    assert res.chm[r, c] == pytest.approx(8.0, abs=0.1)


def test_empty_dsm_cell_falls_back_to_dtm() -> None:
    pts = make_points()
    first = pts["ReturnNumber"] == 1
    far = (pts["X"] > 500040) & (pts["Y"] > 3600040)
    res = build_chm(pts[~(first & far)], BOUNDS, CRS)
    assert float(res.chm[:20, -20:].max()) == 0.0


def test_no_ground_raises() -> None:
    pts = make_points()
    with pytest.raises(SourceError, match="no ground points"):
        build_chm(pts[pts["Classification"] != 2], BOUNDS, CRS)


def test_points_outside_bounds_dropped() -> None:
    pts = make_points(bounds=(499950.0, 3599950.0, 500110.0, 3600110.0), density=2.0)
    pts["Z"][(pts["X"] < 500000) | (pts["Y"] > 3600060)] = 999.0
    res = build_chm(pts, BOUNDS, CRS)
    assert res.chm.shape == (120, 120)
    assert float(res.dtm.max()) < 100.0


def test_building_mask() -> None:
    pts = make_points(plateaus=((500030.0, 3600030.0, 5.0, 8.0, 6),))
    res = build_chm(pts, BOUNDS, CRS)
    assert res.building_mask is not None
    r, c = cell_of(res, 500030.25, 3600030.25)
    assert res.building_mask[r, c]
    assert not res.building_mask[5, 5]
    assert 0.9 < res.building_mask.sum() / (20 * 20) <= 1.0
    off = build_chm(pts, BOUNDS, CRS, use_building_class=False)
    assert off.building_mask is None


def test_tree_over_building_edge_uses_top_return() -> None:
    pts = make_points(
        plateaus=((500030.0, 3600030.0, 5.0, 8.0, 6),),
        cones=((500030.25, 3600030.25, 20.0, 1.5),),
    )
    res = build_chm(pts, BOUNDS, CRS)
    assert res.building_mask is not None
    r, c = cell_of(res, 500030.25, 3600030.25)
    assert not res.building_mask[r, c]  # tree apex (class 1) is above the roof


def test_deterministic_and_order_independent() -> None:
    pts = make_points(cones=((500030.25, 3600030.25, 20.0, 2.0),))
    a = build_chm(pts, BOUNDS, CRS)
    shuffled = pts[np.random.default_rng(3).permutation(len(pts))]
    b = build_chm(shuffled, BOUNDS, CRS)
    assert np.array_equal(a.dsm, b.dsm)
    assert np.allclose(a.dtm, b.dtm, atol=1e-5)
    assert np.allclose(a.chm, b.chm, atol=1e-5)
    assert a.transform == b.transform


def test_smoothing_sigma_zero_is_identity() -> None:
    pts = make_points(cones=((500030.25, 3600030.25, 20.0, 2.0),))
    res = build_chm(pts, BOUNDS, CRS, smooth_sigma_px=0)
    assert np.array_equal(res.chm, res.chm_smooth)


def test_sample_ground_bilinear_and_outside() -> None:
    pts = make_points(slope=0.05)
    res = build_chm(pts, BOUNDS, CRS)
    xs = np.array([500020.0, 500030.1, BOUNDS[0] + 0.1, BOUNDS[2] - 0.1, 499990.0, 500030.0])
    ys = np.array([3600020.0, 3600040.0, 3600005.0, 3600055.0, 3600020.0, 3600070.0])
    got = sample_ground(res, xs, ys)
    expected = 10.0 + 0.05 * (xs - BOUNDS[0])
    assert np.allclose(got[:4], expected[:4], atol=0.15)
    assert np.isnan(got[4]) and np.isnan(got[5])


def test_write_debug_rasters(tmp_path: Path) -> None:
    rasterio = pytest.importorskip("rasterio", reason="rasterio (lidar extra) not installed")
    pts = make_points(plateaus=((500030.0, 3600030.0, 5.0, 8.0, 6),))
    res = build_chm(pts, BOUNDS, CRS)
    write_debug_rasters(res, tmp_path / "dbg")
    names = sorted(p.stem for p in (tmp_path / "dbg").glob("*.tif"))
    assert names == ["building_mask", "chm", "chm_smooth", "dsm", "dtm"]
    with rasterio.open(tmp_path / "dbg" / "chm.tif") as src:
        assert src.transform == res.transform
        assert src.crs.to_epsg() == 32611
        assert np.array_equal(src.read(1), res.chm)


@pytest.mark.slow
def test_performance_540m_tile_6m_points() -> None:
    bounds = (500000.0, 3600000.0, 500540.0, 3600540.0)
    rng = np.random.default_rng(0)
    n = 6_000_000
    pts = np.zeros(n, dtype=DTYPE)
    pts["X"] = rng.uniform(bounds[0], bounds[2], n)
    pts["Y"] = rng.uniform(bounds[1], bounds[3], n)
    ground = rng.random(n) < 0.4
    pts["Z"] = 10.0 + np.where(ground, 0.0, rng.uniform(0, 15, n))
    pts["Classification"] = np.where(ground, 2, 1)
    pts["ReturnNumber"] = np.where(ground, rng.integers(1, 3, n), 1)
    t0 = time.perf_counter()
    res = build_chm(pts, bounds, CRS)
    elapsed = time.perf_counter() - t0
    assert res.chm.shape == (1080, 1080)
    assert elapsed < 30.0, f"build_chm took {elapsed:.1f}s"
