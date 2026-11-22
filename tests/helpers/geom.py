"""Geometry assertions for exclusion polygons (EPSG:4326 lon/lat inputs).

Generic checks on any shapely geometry: they do not depend on palmgen or palmcore. Distances
are WGS84 geodesic (``pyproj.Geod``); areas are measured in an azimuthal equidistant projection
centred on the geometry. Every assertion message gives the measured value and the limit.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from functools import lru_cache
from typing import Any

import numpy as np
from pyproj import CRS, Geod, Transformer
from shapely import transform as _shapely_transform
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

_GEOD = Geod(ellps="WGS84")
_WGS84 = "EPSG:4326"


def distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """WGS84 geodesic distance in metres between two (lon, lat) points."""
    _, _, dist = _GEOD.inv(a[0], a[1], b[0], b[1])
    return float(dist)


@lru_cache(maxsize=256)
def _forward_fn(origin: tuple[float, float]) -> Callable[..., Any]:
    lon, lat = origin
    crs = CRS.from_proj4(f"+proj=aeqd +lat_0={lat!r} +lon_0={lon!r} +datum=WGS84 +units=m +no_defs")
    return Transformer.from_crs(_WGS84, crs, always_xy=True).transform


def to_local_m(geom: BaseGeometry, origin: tuple[float, float]) -> BaseGeometry:
    """Project a lon/lat geometry to metres in an azimuthal equidistant frame centred on origin."""
    fwd = _forward_fn((float(origin[0]), float(origin[1])))

    def apply(coords: np.ndarray) -> np.ndarray:
        x, y = fwd(coords[:, 0], coords[:, 1])
        return np.column_stack([np.asarray(x), np.asarray(y)])

    return _shapely_transform(geom, apply)


def _local_area_m2(geom: BaseGeometry) -> float:
    """Area in m2, measured in an equidistant projection centred on the geometry."""
    if geom.is_empty:
        return 0.0
    c = geom.centroid
    return float(to_local_m(geom, (c.x, c.y)).area)


def _polygon_parts(geom: BaseGeometry) -> list[Polygon]:
    if isinstance(geom, Polygon):
        return [geom]
    if isinstance(geom, MultiPolygon):
        return list(geom.geoms)
    raise TypeError(f"expected Polygon or MultiPolygon, got {geom.geom_type}")


def _coords_of(ring: Any) -> list[tuple[float, ...]]:
    raw = ring.coords if hasattr(ring, "coords") else ring
    return [tuple(float(v) for v in c) for c in raw]


def assert_valid_polygon(
    geom: BaseGeometry, *, allow_multi: bool = True, min_area_m2: float = 0.01
) -> None:
    """Fail unless geom is a non-empty, valid, closed polygon of at least min_area_m2 per part."""
    if geom is None or geom.is_empty:
        raise AssertionError("polygon is empty")
    if not isinstance(geom, (Polygon, MultiPolygon)):
        raise AssertionError(f"expected Polygon or MultiPolygon, got {geom.geom_type}")
    if isinstance(geom, MultiPolygon) and not allow_multi:
        raise AssertionError(f"MultiPolygon with {len(geom.geoms)} parts not allowed here")
    if not geom.is_valid:
        raise AssertionError(f"polygon is invalid: {explain_validity(geom)}")
    for part_index, part in enumerate(_polygon_parts(geom)):
        rings = [part.exterior, *part.interiors]
        for ring_index, ring in enumerate(rings):
            try:
                assert_ring_closed(ring)
            except AssertionError as exc:
                where = f"part {part_index} ring {ring_index}"
                raise AssertionError(f"{where}: {exc}") from None
        area = _local_area_m2(part)
        if area < min_area_m2:
            raise AssertionError(
                f"polygon part {part_index} area {area:.4f} m2 is below minimum {min_area_m2} m2"
            )


def assert_ring_closed(ring: Any) -> None:
    """Fail unless a ring's first and last coordinates are equal.

    Accepts a shapely ring (LinearRing, or anything with ``.coords``) or a raw sequence of
    coordinate tuples. A closed ring needs at least four coordinates.
    """
    coords = _coords_of(ring)
    if len(coords) < 4:
        raise AssertionError(f"ring has {len(coords)} coordinates; a closed ring needs at least 4")
    if coords[0] != coords[-1]:
        raise AssertionError(f"ring is not closed: first {coords[0]} != last {coords[-1]}")


def _exterior_vertices(poly: BaseGeometry) -> list[tuple[float, float]]:
    """Exterior ring vertices without the closing duplicate, as (lon, lat)."""
    if not isinstance(poly, Polygon):
        raise AssertionError(f"expected a single Polygon, got {poly.geom_type}")
    coords = _coords_of(poly.exterior)
    return [(c[0], c[1]) for c in coords[:-1]]


def assert_circle_like(
    poly: BaseGeometry,
    center: tuple[float, float],
    radius_m: float,
    sides: int,
    rel_tol: float = 0.02,
) -> None:
    """Fail unless poly is a closed ``sides``-gon whose vertices sit at about radius_m from center.

    Each vertex distance d must satisfy
    r*cos(pi/sides)*(1-rel_tol) <= d <= r/cos(pi/sides)*(1+rel_tol),
    which accepts both inscribed and circumscribed polygons.
    """
    if not isinstance(poly, Polygon) or poly.is_empty:
        raise AssertionError(f"expected a non-empty Polygon, got {poly.geom_type}")
    if poly.interiors:
        raise AssertionError(f"circle-like polygon has {len(poly.interiors)} holes; expected none")
    coords = _coords_of(poly.exterior)
    if len(coords) != sides + 1:
        raise AssertionError(
            f"ring has {len(coords)} coordinates; expected {sides + 1} "
            f"({sides} sides plus closing point)"
        )
    assert_ring_closed(coords)
    lower = radius_m * math.cos(math.pi / sides) * (1 - rel_tol)
    upper = radius_m / math.cos(math.pi / sides) * (1 + rel_tol)
    dists = [distance_m(center, (c[0], c[1])) for c in coords[:-1]]
    bad = [(i, d) for i, d in enumerate(dists) if not lower <= d <= upper]
    if bad:
        i, d = max(bad, key=lambda item: abs(item[1] - radius_m))
        raise AssertionError(
            f"vertex {i} is {d:.4f} m from center; allowed [{lower:.4f}, {upper:.4f}] m "
            f"for radius {radius_m} m, {sides} sides, rel_tol {rel_tol} "
            f"({len(bad)} of {len(dists)} vertices out of range)"
        )


def assert_radius_within(
    poly: BaseGeometry,
    center: tuple[float, float],
    r_min_m: float,
    r_max_m: float,
) -> None:
    """Fail unless every exterior vertex lies within [r_min_m, r_max_m] metres of center."""
    dists = [distance_m(center, v) for v in _exterior_vertices(poly)]
    if not dists:
        raise AssertionError("polygon has no vertices")
    lo, hi = min(dists), max(dists)
    if hi > r_max_m:
        raise AssertionError(f"max vertex radius {hi:.4f} m exceeds limit {r_max_m} m")
    if lo < r_min_m:
        raise AssertionError(f"min vertex radius {lo:.4f} m is below limit {r_min_m} m")


def assert_disjoint_from(
    poly: BaseGeometry,
    others: Iterable[BaseGeometry] | BaseGeometry,
    *,
    tol_m2: float = 0.01,
) -> None:
    """Fail if poly overlaps any geometry in others by more than tol_m2 square metres."""
    if isinstance(others, BaseGeometry):
        others = [others]
    for index, other in enumerate(others):
        if other is None or other.is_empty:
            continue
        overlap = _local_area_m2(poly.intersection(other))
        if overlap > tol_m2:
            raise AssertionError(
                f"polygon overlaps others[{index}] by {overlap:.4f} m2; limit {tol_m2} m2"
            )


def assert_points_close(a: tuple[float, float], b: tuple[float, float], tol_m: float) -> None:
    """Fail unless the geodesic distance between a and b is at most tol_m metres."""
    d = distance_m(a, b)
    if d > tol_m:
        raise AssertionError(f"points are {d:.4f} m apart; limit {tol_m} m")
