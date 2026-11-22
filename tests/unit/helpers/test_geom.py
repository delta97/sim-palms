"""Self-tests for tests/helpers/geom.py: one pass and one fail case per helper."""

from __future__ import annotations

import math

import numpy as np
import pytest
from pyproj import CRS, Geod, Transformer
from shapely.geometry import Polygon, box

from tests.helpers.geom import (
    assert_circle_like,
    assert_disjoint_from,
    assert_points_close,
    assert_radius_within,
    assert_ring_closed,
    assert_valid_polygon,
    distance_m,
    to_local_m,
)

ORIGIN = (-117.25, 32.75)
_GEOD = Geod(ellps="WGS84")


def ngon(center: tuple[float, float], radius_m: float, sides: int) -> Polygon:
    """Inscribed n-gon whose vertices are at geodesic distance radius_m from center."""
    pts = []
    for k in range(sides):
        lon, lat, _ = _GEOD.fwd(center[0], center[1], 360.0 * k / sides, radius_m)
        pts.append((lon, lat))
    return Polygon(pts)


def local_to_lonlat(points_m: list[tuple[float, float]], origin: tuple[float, float]) -> Polygon:
    """Build a lon/lat polygon from metres in the aeqd frame centred on origin."""
    crs = CRS.from_proj4(
        f"+proj=aeqd +lat_0={origin[1]!r} +lon_0={origin[0]!r} +datum=WGS84 +units=m +no_defs"
    )
    inverse = Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform
    coords = np.asarray(points_m, dtype=float)
    x, y = inverse(coords[:, 0], coords[:, 1])
    return Polygon(np.column_stack([x, y]))


# --- distance_m / assert_points_close ----------------------------------------------------


def test_distance_m_one_millidegree_latitude() -> None:
    a = (-117.25, 32.75)
    b = (-117.25, 32.751)
    assert distance_m(a, b) == pytest.approx(110.9, abs=0.5)


def test_assert_points_close_passes_and_fails() -> None:
    a = (-117.25, 32.75)
    assert_points_close(a, (-117.25, 32.751), tol_m=111.0)
    with pytest.raises(AssertionError, match=r"110\.\d+ m apart; limit 1\.0 m"):
        assert_points_close(a, (-117.25, 32.751), tol_m=1.0)


def test_to_local_m_origin_maps_to_zero() -> None:
    local = to_local_m(Polygon([ORIGIN, (ORIGIN[0] + 0.0001, ORIGIN[1]), ORIGIN]), ORIGIN)
    assert abs(local.bounds[0]) < 1e-6 and abs(local.bounds[1]) < 1e-6


# --- assert_ring_closed ------------------------------------------------------------------


def test_ring_closed_passes_on_closed_sequence() -> None:
    ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)]
    assert_ring_closed(ring)


def test_ring_closed_fails_when_last_differs_from_first() -> None:
    ring = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    with pytest.raises(AssertionError, match="not closed"):
        assert_ring_closed(ring)


def test_ring_closed_rejects_too_few_coordinates() -> None:
    with pytest.raises(AssertionError, match="needs at least 4"):
        assert_ring_closed([(0.0, 0.0), (1.0, 0.0), (0.0, 0.0)])


# --- assert_valid_polygon ----------------------------------------------------------------


def test_valid_polygon_passes() -> None:
    assert_valid_polygon(ngon(ORIGIN, 3.4, 12))


def test_bow_tie_fails_validity() -> None:
    bow = Polygon([(0.0, 0.0), (1.0, 1.0), (1.0, 0.0), (0.0, 1.0)])
    with pytest.raises(AssertionError, match="invalid: Self-intersection"):
        assert_valid_polygon(bow, min_area_m2=0.0)


def test_empty_polygon_fails() -> None:
    with pytest.raises(AssertionError, match="empty"):
        assert_valid_polygon(Polygon())


def test_tiny_polygon_fails_min_area() -> None:
    tiny = ngon(ORIGIN, 0.05, 12)  # about 0.0076 m2
    with pytest.raises(AssertionError, match=r"area .* m2 is below minimum 0\.01 m2"):
        assert_valid_polygon(tiny)


def test_multipolygon_rejected_when_not_allowed() -> None:
    a = ngon(ORIGIN, 3.4, 12)
    b = ngon((ORIGIN[0] + 0.001, ORIGIN[1]), 3.4, 12)
    from shapely.geometry import MultiPolygon

    multi = MultiPolygon([a, b])
    assert_valid_polygon(multi)
    with pytest.raises(AssertionError, match="not allowed"):
        assert_valid_polygon(multi, allow_multi=False)


# --- assert_circle_like / assert_radius_within -------------------------------------------


def test_12gon_at_exact_radius_is_circle_like_and_valid() -> None:
    poly = ngon(ORIGIN, 3.4, 12)
    assert_circle_like(poly, ORIGIN, 3.4, sides=12)
    assert_valid_polygon(poly)


def test_12gon_at_1_1x_radius_fails_circle_like_and_radius_bound() -> None:
    poly = ngon(ORIGIN, 3.4 * 1.1, 12)
    with pytest.raises(AssertionError, match="allowed"):
        assert_circle_like(poly, ORIGIN, 3.4, sides=12)
    with pytest.raises(AssertionError, match=r"max vertex radius 3\.7\d+ m exceeds limit 3\.5 m"):
        assert_radius_within(poly, ORIGIN, r_min_m=0.0, r_max_m=3.5)


def test_circle_like_rejects_wrong_vertex_count() -> None:
    poly = ngon(ORIGIN, 3.4, 8)
    with pytest.raises(AssertionError, match="expected 13"):
        assert_circle_like(poly, ORIGIN, 3.4, sides=12)


def test_circle_like_accepts_circumscribed_polygon() -> None:
    r = 3.4
    circum = ngon(ORIGIN, r / math.cos(math.pi / 12), 12)
    assert_circle_like(circum, ORIGIN, r, sides=12)


def test_radius_within_passes_for_exact_circle() -> None:
    poly = ngon(ORIGIN, 3.4, 12)
    assert_radius_within(poly, ORIGIN, r_min_m=3.0, r_max_m=3.5)


def test_radius_within_fails_below_minimum() -> None:
    poly = ngon(ORIGIN, 3.4, 12)
    with pytest.raises(AssertionError, match=r"below limit 3\.5 m"):
        assert_radius_within(poly, ORIGIN, r_min_m=3.5, r_max_m=10.0)


# --- assert_disjoint_from ----------------------------------------------------------------


def _building_and_overlap() -> tuple[Polygon, Polygon]:
    building = local_to_lonlat([(0, 0), (10, 0), (10, 10), (0, 10)], ORIGIN)
    # Overlaps the building's east edge by [9, 10] x [4, 5] = 1 m2.
    palm = local_to_lonlat([(9, 4), (11, 4), (11, 5), (9, 5)], ORIGIN)
    return building, palm


def test_disjoint_fails_on_one_m2_overlap_with_building() -> None:
    building, palm = _building_and_overlap()
    with pytest.raises(AssertionError, match=r"others\[0\] by 1\.0000 m2"):
        assert_disjoint_from(palm, [building])


def test_disjoint_passes_after_difference() -> None:
    building, palm = _building_and_overlap()
    clipped = palm.difference(building)
    assert_disjoint_from(clipped, [building])
    assert_valid_polygon(clipped, min_area_m2=0.01)


def test_disjoint_reports_index_of_offending_geometry() -> None:
    far = box(ORIGIN[0] + 0.01, ORIGIN[1], ORIGIN[0] + 0.011, ORIGIN[1] + 0.001)
    building, palm = _building_and_overlap()
    with pytest.raises(AssertionError, match=r"others\[1\]"):
        assert_disjoint_from(palm, [far, building])
