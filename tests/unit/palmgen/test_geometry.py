from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pytest
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from palmgen.errors import GenerationError
from palmgen.geometry import (
    RADIUS_CLAMPED,
    RADIUS_DEFAULTED,
    LocalProjection,
    circle_polygon,
    merge_clusters,
    normalize_ring,
    palm_radius,
    simplify_cluster,
    vertex_count,
)
from palmgen.model import Palm


@dataclass(frozen=True)
class Cfg:
    margin_m: float = 1.5
    default_radius_m: float = 3.0
    radius_min_m: float = 1.0
    radius_max_m: float = 8.0


def palm(crown: float | None = None, radius: float | None = None, palm_id: str = "p1") -> Palm:
    return Palm(palm_id, -117.25, 32.75, "washingtonia", None, crown, radius, False)


def row(n: int, spacing: float, r: float = 1.0, y: float = 0.0) -> list[tuple[str, Polygon]]:
    return [(f"p{i:04d}", circle_polygon(i * spacing, y, r)) for i in range(n)]


def diag(poly: Polygon) -> float:
    minx, miny, maxx, maxy = poly.bounds
    return math.hypot(maxx - minx, maxy - miny)


# --- LocalProjection ---------------------------------------------------------------------


def test_projection_origin_and_round_trip() -> None:
    proj = LocalProjection(-117.25, 32.75)
    x, y = proj.forward(-117.25, 32.75)
    assert abs(x) < 1e-6 and abs(y) < 1e-6
    lon, lat = proj.inverse(*proj.forward(-117.2431, 32.7612))
    assert lon == pytest.approx(-117.2431, abs=1e-9)
    assert lat == pytest.approx(32.7612, abs=1e-9)


def test_projection_is_metric() -> None:
    proj = LocalProjection(-117.25, 32.75)
    x0, y0 = proj.forward(-117.25, 32.75)
    x1, y1 = proj.forward(-117.25, 32.75 + 0.001)
    assert abs(x1 - x0) < 1e-3
    assert y1 - y0 == pytest.approx(110.9, abs=0.5)  # ~111 km per degree of latitude


def test_projection_geometry_round_trip() -> None:
    proj = LocalProjection(-117.25, 32.75)
    poly = Polygon([(-117.251, 32.751), (-117.250, 32.751), (-117.250, 32.752)])
    local = proj.geom_to_local(poly)
    assert 5000 < local.area < 5500
    back = proj.geom_to_lonlat(local)
    assert back.symmetric_difference(poly).area < 1e-14


# --- palm_radius -------------------------------------------------------------------------


def test_radius_precedence() -> None:
    cfg = Cfg()
    assert palm_radius(palm(crown=4.0, radius=5.0), cfg, 2.0) == (4.0, None)  # override wins
    assert palm_radius(palm(crown=4.0, radius=5.0), cfg, None) == (5.0, None)
    assert palm_radius(palm(crown=4.0), cfg, None) == (3.5, None)
    assert palm_radius(palm(radius=5.0), cfg, 2.0) == (5.0, None)  # override needs a crown
    assert palm_radius(palm(), cfg, 2.0) == (3.0, RADIUS_DEFAULTED)


def test_radius_clamped() -> None:
    cfg = Cfg()
    assert palm_radius(palm(radius=0.2), cfg, None) == (1.0, RADIUS_CLAMPED)
    assert palm_radius(palm(crown=30.0), cfg, None) == (8.0, RADIUS_CLAMPED)
    assert palm_radius(palm(), Cfg(default_radius_m=20.0), None) == (8.0, RADIUS_CLAMPED)


# --- circle_polygon ----------------------------------------------------------------------


def test_circle_polygon_shape() -> None:
    poly = circle_polygon(10.0, -5.0, 2.0)
    assert poly.is_valid and not poly.is_empty
    assert poly.exterior.is_ccw
    coords = list(poly.exterior.coords)
    assert coords[0] == coords[-1]
    assert vertex_count(poly) == 12
    first = poly.exterior.coords[0]  # vertex 0 is due east of the centre
    assert first[0] == pytest.approx(10.0 + 2.0 / math.cos(math.pi / 12))
    assert first[1] == pytest.approx(-5.0)


@pytest.mark.parametrize("sides", [6, 12, 16, 32])
def test_circle_contains_true_circle(sides: int) -> None:
    poly = circle_polygon(3.0, 4.0, 2.5, sides=sides)
    true_circle = Point(3.0, 4.0).buffer(2.5, quad_segs=128)
    assert poly.buffer(1e-9).contains(true_circle)
    assert vertex_count(poly) == sides


def test_circle_inscribed_option() -> None:
    poly = circle_polygon(0.0, 0.0, 1.0, sides=12, circumscribe=False)
    assert poly.exterior.coords[0][0] == pytest.approx(1.0)


# --- merge_clusters ----------------------------------------------------------------------


def test_row_3m_apart_merges_by_edge_gap() -> None:
    # Radius 1 m circles 3 m apart are ~0.93 m apart edge to edge: separate for gap 0.5,
    # merged for gap 2 (the gap is measured between circle edges, not centres).
    assert len(merge_clusters(row(5, 3.0), 0.5, 150.0)) == 5
    assert len(merge_clusters(row(5, 3.0), 2.0, 150.0)) == 1


def test_row_1_5m_apart_merges() -> None:
    clusters = merge_clusters(row(5, 1.5), 0.5, 150.0)
    assert len(clusters) == 1
    assert clusters[0].member_ids == tuple(f"p{i:04d}" for i in range(5))
    assert isinstance(clusters[0].polygon_local, Polygon)


def test_every_member_circle_is_covered() -> None:
    rng = random.Random(7)
    items = [
        (f"p{i:03d}", circle_polygon(rng.uniform(0, 40), rng.uniform(0, 40), rng.uniform(1, 3)))
        for i in range(60)
    ]
    by_id = dict(items)
    clusters = merge_clusters(items, 2.0, 1000.0)
    assert sorted(i for c in clusters for i in c.member_ids) == sorted(by_id)
    for c in clusters:
        assert c.polygon_local.is_valid and not c.polygon_local.is_empty
        assert c.member_ids == tuple(sorted(c.member_ids))
        for pid in c.member_ids:
            assert by_id[pid].difference(c.polygon_local).area < 1e-6


def test_hull_bridges_a_gap_between_circles() -> None:
    items = [("a", circle_polygon(0.0, 0.0, 1.0)), ("b", circle_polygon(4.0, 0.0, 1.0))]
    (cluster,) = merge_clusters(items, 2.5, 150.0)
    assert cluster.polygon_local.contains(Point(2.0, 0.0))  # between the circles


def test_single_palm_has_exactly_sides_vertices() -> None:
    for sides in (8, 12, 20):
        circle = circle_polygon(5.0, 5.0, 2.0, sides=sides)
        (cluster,) = merge_clusters([("only", circle)], 2.0, 150.0)
        assert cluster.member_ids == ("only",)
        assert vertex_count(cluster.polygon_local) == sides
        assert cluster.polygon_local.equals(circle)


def test_split_long_row() -> None:
    items = row(134, 3.0)  # about 400 m long, all one component for gap 2
    report: list[tuple[str, ...]] = []
    clusters = merge_clusters(items, 2.0, 150.0, split_report=report)
    assert len(clusters) >= 3
    assert all(diag(c.polygon_local) <= 150.0 for c in clusters)
    assert sorted(i for c in clusters for i in c.member_ids) == sorted(i for i, _ in items)
    assert report == [tuple(i for i, _ in items)]
    by_id = dict(items)
    for c in clusters:
        for pid in c.member_ids:
            assert by_id[pid].difference(c.polygon_local).area < 1e-6


def test_split_cuts_longest_edge_first() -> None:
    # Two tight triples joined by one longer link: the link is the edge that goes.
    items = [
        ("a1", circle_polygon(0.0, 0.0, 1.0)),
        ("a2", circle_polygon(2.0, 0.0, 1.0)),
        ("a3", circle_polygon(4.0, 0.0, 1.0)),
        ("b1", circle_polygon(8.0, 0.0, 1.0)),
        ("b2", circle_polygon(10.0, 0.0, 1.0)),
        ("b3", circle_polygon(12.0, 0.0, 1.0)),
    ]
    clusters = merge_clusters(items, 2.5, 8.0)
    assert [c.member_ids for c in clusters] == [("a1", "a2", "a3"), ("b1", "b2", "b3")]


def test_no_split_report_when_within_limit() -> None:
    report: list[tuple[str, ...]] = []
    merge_clusters(row(5, 1.5), 0.5, 150.0, split_report=report)
    assert report == []


def test_shuffled_input_gives_identical_output() -> None:
    rng = random.Random(11)
    items = [
        (f"p{i:03d}", circle_polygon(rng.uniform(0, 60), rng.uniform(0, 60), rng.uniform(1, 2)))
        for i in range(80)
    ]
    expected = merge_clusters(items, 2.0, 40.0)
    for seed in range(5):
        shuffled = list(items)
        random.Random(seed).shuffle(shuffled)
        got = merge_clusters(shuffled, 2.0, 40.0)
        assert [c.member_ids for c in got] == [c.member_ids for c in expected]
        assert [c.polygon_local.wkb for c in got] == [c.polygon_local.wkb for c in expected]


def test_shuffled_equal_spacing_row_split_is_identical() -> None:
    items = row(134, 3.0)
    expected = merge_clusters(items, 2.0, 150.0)
    shuffled = list(items)
    random.Random(3).shuffle(shuffled)
    got = merge_clusters(shuffled, 2.0, 150.0)
    assert [c.member_ids for c in got] == [c.member_ids for c in expected]


def test_clusters_sorted_by_first_member_id() -> None:
    items = [("z", circle_polygon(0.0, 0.0, 1.0)), ("a", circle_polygon(100.0, 0.0, 1.0))]
    assert [c.member_ids for c in merge_clusters(items, 2.0, 150.0)] == [("a",), ("z",)]


def test_merge_edge_cases() -> None:
    assert merge_clusters([], 2.0, 150.0) == []
    dup = [("a", circle_polygon(0.0, 0.0, 1.0)), ("a", circle_polygon(9.0, 0.0, 1.0))]
    with pytest.raises(GenerationError):
        merge_clusters(dup, 2.0, 150.0)


def test_union_of_clusters_covers_all_circles() -> None:
    items = row(20, 2.0)
    clusters = merge_clusters(items, 2.0, 150.0)
    union = unary_union([c.polygon_local for c in clusters])
    assert unary_union([p for _, p in items]).difference(union).area < 1e-6


# --- simplify_cluster --------------------------------------------------------------------


def test_simplify_drops_collinear_vertices() -> None:
    poly = Polygon([(0, 0), (5, 0), (10, 0), (10, 10), (0, 10)])
    out, flag = simplify_cluster(poly, 0.1, 256)
    assert vertex_count(out) == 4
    assert flag is False


def test_simplify_keeps_circle_at_default_tolerance() -> None:
    circle = circle_polygon(0.0, 0.0, 1.0)
    out, flag = simplify_cluster(circle, 0.1, 256)
    assert vertex_count(out) == 12 and flag is False


def test_simplify_doubles_tolerance_over_limit() -> None:
    circle = circle_polygon(0.0, 0.0, 5.0, sides=200)
    out, flag = simplify_cluster(circle, 0.01, 60)
    assert flag is True
    assert vertex_count(out) <= 60
    assert out.is_valid


def test_simplify_raises_when_still_too_large() -> None:
    circle = circle_polygon(0.0, 0.0, 50.0, sides=400)
    with pytest.raises(GenerationError):
        simplify_cluster(circle, 0.0001, 8)


# --- normalize_ring ----------------------------------------------------------------------


def test_normalize_ring_rotation_orientation_and_closing() -> None:
    # Square given clockwise, starting at the north-east corner.
    square = Polygon([(2.0, 2.0), (2.0, 1.0), (1.0, 1.0), (1.0, 2.0)])
    ccw = normalize_ring(square, "ccw", 8, closed=False)
    assert ccw == ((1.0, 1.0), (2.0, 1.0), (2.0, 2.0), (1.0, 2.0))
    cw = normalize_ring(square, "cw", 8, closed=True)
    assert cw == ((1.0, 1.0), (1.0, 2.0), (2.0, 2.0), (2.0, 1.0), (1.0, 1.0))


def test_normalize_ring_rounds_and_drops_duplicates() -> None:
    poly = Polygon([(0.000000001, 0.0), (1.0, 0.0), (1.000000002, 0.000000001), (1.0, 1.0)])
    ring = normalize_ring(poly, "ccw", 6, closed=False)
    assert ring == ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0))


def test_normalize_ring_no_negative_zero() -> None:
    poly = Polygon([(-1e-12, -1e-12), (1.0, 0.0), (1.0, 1.0)])
    ring = normalize_ring(poly, "ccw", 6, closed=False)
    assert all(math.copysign(1.0, v) == 1.0 for pt in ring for v in pt)


def test_normalize_ring_independent_of_start_vertex() -> None:
    coords = [(0.0, 0.0), (3.0, 0.0), (3.0, 2.0), (1.0, 3.0), (0.0, 2.0)]
    expected = normalize_ring(Polygon(coords), "ccw", 8, closed=True)
    for k in range(len(coords)):
        rotated = coords[k:] + coords[:k]
        assert normalize_ring(Polygon(rotated), "ccw", 8, closed=True) == expected
        assert normalize_ring(Polygon(rotated[::-1]), "ccw", 8, closed=True) == expected


def test_normalize_ring_rejects_bad_input() -> None:
    tiny = Polygon([(0.0, 0.0), (1e-9, 0.0), (0.0, 1e-9)])
    with pytest.raises(GenerationError):
        normalize_ring(tiny, "ccw", 6, closed=False)
    holed = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], [[(4, 4), (6, 4), (6, 6), (4, 6)]])
    with pytest.raises(GenerationError):
        normalize_ring(holed, "ccw", 6, closed=False)
    with pytest.raises(ValueError):
        normalize_ring(Polygon([(0, 0), (1, 0), (1, 1)]), "up", 6, closed=False)


def test_pipeline_end_to_end_ring_is_stable() -> None:
    proj = LocalProjection(-117.25, 32.75)
    lonlat = [(-117.25 + i * 0.00002, 32.75) for i in range(6)]
    items = []
    for i, (lon, lat) in enumerate(lonlat):
        x, y = proj.forward(lon, lat)
        items.append((f"p{i}", circle_polygon(x, y, 1.0)))
    (cluster,) = merge_clusters(items, 2.0, 150.0)
    poly, _ = simplify_cluster(cluster.polygon_local, 0.1, 256)
    ring = normalize_ring(proj.geom_to_lonlat(poly), "ccw", 8, closed=False)
    again = normalize_ring(
        proj.geom_to_lonlat(simplify_cluster(cluster.polygon_local, 0.1, 256)[0]),
        "ccw",
        8,
        closed=False,
    )
    assert ring == again
    assert min(ring) == ring[0]
