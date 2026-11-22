from __future__ import annotations

import random

import pytest
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from palmgen.geometry import (
    ClipResult,
    circle_polygon,
    clip_buildings,
    merge_clusters,
    remove_holes,
)
from palmgen.model import Cluster

BUF = 0.3
MIN_AREA = 1.0
OVERLAP_TOL = 1e-6

Points = dict[str, tuple[float, float]]


def _single(pid: str, x: float, y: float, r: float = 3.0) -> tuple[Cluster, Points]:
    return Cluster((pid,), circle_polygon(x, y, r)), {pid: (x, y)}


def _check_parts(res: ClipResult, footprints: list[Polygon]) -> None:
    buffered = unary_union([f.buffer(BUF) for f in footprints]) if footprints else Polygon()
    for cluster, _part, _members in res.parts:
        p = cluster.polygon_local
        assert isinstance(p, Polygon)
        assert p.is_valid and not p.is_empty
        assert p.area >= MIN_AREA
        assert p.intersection(buffered).area < OVERLAP_TOL


def test_circle_half_over_building_has_no_overlap() -> None:
    cluster, pts = _single("p1", 0.0, 0.0)
    bld = box(0.0, -10.0, 10.0, 10.0)
    res = clip_buildings([cluster], [bld], BUF, MIN_AREA, palm_points_local=pts)
    assert len(res.parts) == 1
    _check_parts(res, [bld])
    # the palm sits on the footprint edge, inside the buffered footprint: no cut for it
    assert res.in_building == ["p1"]
    assert res.parts[0][2] == []


def test_palm_beside_building_keeps_cut_clear_of_wall() -> None:
    cluster, pts = _single("p1", -2.0, 0.0)
    bld = box(0.0, -10.0, 10.0, 10.0)
    res = clip_buildings([cluster], [bld], BUF, MIN_AREA, palm_points_local=pts)
    assert len(res.parts) == 1 and res.parts[0][2] == ["p1"]
    assert res.in_building == []
    _check_parts(res, [bld])
    assert res.parts[0][0].polygon_local.bounds[2] <= -BUF + 1e-9


def test_palm_inside_building_is_listed_and_has_no_polygon() -> None:
    cluster, pts = _single("p1", 5.0, 5.0)
    bld = box(0.0, 0.0, 10.0, 10.0)
    res = clip_buildings([cluster], [bld], BUF, MIN_AREA, palm_points_local=pts)
    assert res.parts == []
    assert res.in_building == ["p1"]


def test_building_splitting_cluster_gives_two_parts_with_stable_numbering() -> None:
    items = [(f"p{i}", circle_polygon(i * 3.0, 0.0, 1.0)) for i in range(5)]
    (cluster,) = merge_clusters(items, 1.5, 150.0)
    pts = {f"p{i}": (i * 3.0, 0.0) for i in range(5)}
    wall = box(5.0, -5.0, 7.0, 5.0)  # covers p2 (x=6), cuts p1 (x=3) from p3 (x=9)
    res = clip_buildings([cluster], [wall], BUF, MIN_AREA, palm_points_local=pts)
    assert [p[1] for p in res.parts] == [0, 1]
    assert res.parts[0][2] == ["p0", "p1"]
    assert res.parts[1][2] == ["p3", "p4"]
    assert res.in_building == ["p2"]
    assert all(c.member_ids == cluster.member_ids for c, _, _ in res.parts)
    _check_parts(res, [wall])
    again = clip_buildings([cluster], [wall], BUF, MIN_AREA, palm_points_local=pts)
    assert [(c.polygon_local.wkt, n, m) for c, n, m in again.parts] == [
        (c.polygon_local.wkt, n, m) for c, n, m in res.parts
    ]


def test_footprint_inside_circle_hole_removed_and_area_preserved() -> None:
    cluster, pts = _single("p1", 0.0, 0.0, r=5.0)
    bld = box(-1.0, -1.0, 1.0, 1.0)
    holed = cluster.polygon_local.difference(bld.buffer(BUF))
    assert len(holed.interiors) == 1
    res = clip_buildings([cluster], [bld], BUF, MIN_AREA, palm_points_local=pts)
    assert len(res.parts) == 2
    polys = [c.polygon_local for c, _, _ in res.parts]
    assert all(len(p.interiors) == 0 for p in polys)
    assert unary_union(polys).symmetric_difference(holed).area < OVERLAP_TOL
    _check_parts(res, [bld])
    assert res.in_building == ["p1"]  # the circle centre is inside the building


def test_supports_holes_keeps_the_ring() -> None:
    cluster, _ = _single("p1", 0.0, 0.0, r=5.0)
    pts = {"p1": (3.0, 0.0)}
    bld = box(-1.0, -1.0, 1.0, 1.0)
    res = clip_buildings(
        [cluster], [bld], BUF, MIN_AREA, supports_holes=True, palm_points_local=pts
    )
    assert len(res.parts) == 1
    assert len(res.parts[0][0].polygon_local.interiors) == 1


def test_small_fragment_is_dropped_and_counted() -> None:
    cluster, pts = _single("p1", 0.0, 0.0, r=3.0)
    bld = box(-10.0, -10.0, 2.5 - BUF, 10.0)  # leaves a thin sliver of the circle on the right
    res = clip_buildings([cluster], [bld], BUF, 50.0, palm_points_local=pts)
    assert res.parts == []
    assert res.too_small == 1
    assert res.in_building == ["p1"]


def test_no_footprints_leaves_cluster_untouched() -> None:
    cluster, pts = _single("p1", 0.0, 0.0)
    res = clip_buildings([cluster], [], BUF, MIN_AREA, palm_points_local=pts)
    assert len(res.parts) == 1
    assert res.parts[0][0].polygon_local.equals(cluster.polygon_local)
    assert res.parts[0][1:] == (0, ["p1"])


def test_conflict_without_footprint_is_reported() -> None:
    a, pa = _single("a", 0.0, 0.0)
    b, pb = _single("b", 100.0, 0.0)
    c, pc = _single("c", 200.0, 0.0)
    bld = box(99.0, -1.0, 101.0, 1.0)
    res = clip_buildings(
        [a, b, c],
        [bld],
        BUF,
        MIN_AREA,
        conflict_ids={"a", "b"},
        palm_points_local={**pa, **pb, **pc},
    )
    assert res.conflict_no_footprint == ["a"]  # b hit a footprint; c was not flagged


def test_cluster_and_footprint_order_do_not_matter() -> None:
    cs = [_single(f"p{i}", i * 20.0, 0.0) for i in range(4)]
    pts = {k: v for _, d in cs for k, v in d.items()}
    clusters = [c for c, _ in cs]
    blds = [box(i * 20.0 + 1.0, -3.0, i * 20.0 + 3.0, 3.0) for i in range(4)]
    a = clip_buildings(clusters, blds, BUF, MIN_AREA, palm_points_local=pts)
    b = clip_buildings(clusters[::-1], blds[::-1], BUF, MIN_AREA, palm_points_local=pts)
    assert a == b


def test_remove_holes_without_holes_is_identity() -> None:
    p = box(0.0, 0.0, 4.0, 4.0)
    assert remove_holes(p) == [p]


def test_remove_holes_multiple_holes_preserves_area() -> None:
    outer = box(0.0, 0.0, 30.0, 10.0)
    holes = [box(3.0, 3.0, 6.0, 6.0), box(12.0, 2.0, 15.0, 8.0), box(20.0, 4.0, 27.0, 5.0)]
    poly = Polygon(outer.exterior.coords, [h.exterior.coords for h in holes])
    parts = remove_holes(poly)
    assert len(parts) >= 4
    assert all(len(p.interiors) == 0 and p.is_valid and not p.is_empty for p in parts)
    assert abs(sum(p.area for p in parts) - poly.area) < OVERLAP_TOL
    assert unary_union(parts).symmetric_difference(poly).area < OVERLAP_TOL
    assert [p.bounds[:2] for p in parts] == sorted(p.bounds[:2] for p in parts)


def test_remove_holes_concave_hole() -> None:
    hole = [(4, 2), (8, 2), (8, 4), (5, 4), (5, 8), (8, 8), (8, 9), (4, 9)]  # a C shape
    poly = Polygon(box(0, 0, 12, 12).exterior.coords, [hole])
    parts = remove_holes(poly)
    assert all(len(p.interiors) == 0 and p.is_valid for p in parts)
    assert unary_union(parts).symmetric_difference(poly).area < OVERLAP_TOL


@pytest.mark.parametrize("seed", [20260101])
def test_random_layouts_property(seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(200):
        n = rng.randint(1, 12)
        palms = {f"p{i:03d}": (rng.uniform(0, 40), rng.uniform(0, 40)) for i in range(n)}
        items = [
            (pid, circle_polygon(x, y, rng.uniform(1.0, 5.0))) for pid, (x, y) in palms.items()
        ]
        clusters = merge_clusters(items, 1.0, 150.0)
        blds: list[Polygon] = []
        for _b in range(rng.randint(0, 6)):
            x0, y0 = rng.uniform(-5, 45), rng.uniform(-5, 45)
            blds.append(box(x0, y0, x0 + rng.uniform(1, 15), y0 + rng.uniform(1, 15)))
        res = clip_buildings(clusters, blds, BUF, MIN_AREA, palm_points_local=palms)
        _check_parts(res, blds)
        for c, _n, members in res.parts:
            assert len(c.polygon_local.interiors) == 0
            for m in members:
                assert c.polygon_local.covers(Point(palms[m]))
        assigned = [m for _, _, ms in res.parts for m in ms]
        assert sorted(assigned + res.in_building) == sorted(palms)
