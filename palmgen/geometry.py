"""Exclusion geometry: radii, circumscribed circles, merging, simplification, ring output.

All metric work happens in a :class:`LocalProjection` (transverse Mercator centred on the region).
Every function here is deterministic: inputs are sorted by ``palm_id`` before any geometry is
built, ties are broken by ``palm_id``, and ``normalize_ring`` rounds and canonicalises the ring,
so the same palms give the same polygons whatever the input order.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final, Protocol

import numpy as np
import pyproj
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from palmgen.errors import GenerationError
from palmgen.model import Cluster, Palm

RADIUS_DEFAULTED: Final = "RADIUS_DEFAULTED"
RADIUS_CLAMPED: Final = "RADIUS_CLAMPED"

_DIST_DECIMALS: Final = 6  # distances closer than 1 micrometre tie (then palm_id decides)
_MAX_DOUBLINGS: Final = 5


class RadiusConfig(Protocol):
    """The ``exclusion.*`` values :func:`palm_radius` reads (satisfied by ``GenConfig``)."""

    # Read-only members, so frozen dataclasses and property-backed configs both satisfy it.
    @property
    def margin_m(self) -> float: ...

    @property
    def default_radius_m(self) -> float: ...

    @property
    def radius_min_m(self) -> float: ...

    @property
    def radius_max_m(self) -> float: ...


class LocalProjection:
    """Transverse Mercator centred on ``(lon0, lat0)``, WGS84, metres."""

    def __init__(self, lon0: float, lat0: float) -> None:
        self.lon0 = lon0
        self.lat0 = lat0
        self.crs = pyproj.CRS.from_proj4(
            f"+proj=tmerc +lat_0={lat0!r} +lon_0={lon0!r} +k=1 +x_0=0 +y_0=0 "
            "+ellps=WGS84 +units=m +no_defs"
        )
        self._fwd = pyproj.Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)
        self._inv = pyproj.Transformer.from_crs(self.crs, "EPSG:4326", always_xy=True)

    def forward(self, lon: float, lat: float) -> tuple[float, float]:
        x, y = self._fwd.transform(lon, lat)
        return (float(x), float(y))

    def inverse(self, x: float, y: float) -> tuple[float, float]:
        lon, lat = self._inv.transform(x, y)
        return (float(lon), float(lat))

    def geom_to_local(self, g: Any) -> Any:
        """Transform any shapely geometry from lon/lat to local metres."""
        return shapely.transform(g, lambda c: _apply(self._fwd, c))

    def geom_to_lonlat(self, g: Any) -> Any:
        """Transform any shapely geometry from local metres to lon/lat."""
        return shapely.transform(g, lambda c: _apply(self._inv, c))


def _apply(tr: pyproj.Transformer, coords: Any) -> Any:
    xs, ys = tr.transform(coords[:, 0], coords[:, 1])
    return np.column_stack((xs, ys))


def palm_radius(
    p: Palm, cfg: RadiusConfig, margin_override: float | None
) -> tuple[float, str | None]:
    """Exclusion radius in metres and a warning code (``None`` when nothing needed fixing).

    Precedence: ``margin_override`` with a crown, then ``exclusion_radius_m``, then crown plus
    ``cfg.margin_m``, then ``cfg.default_radius_m`` (``RADIUS_DEFAULTED``). The result is clamped
    to ``[radius_min_m, radius_max_m]`` (``RADIUS_CLAMPED``, which wins over ``RADIUS_DEFAULTED``).
    """
    warning: str | None = None
    if margin_override is not None and p.crown_diam_m is not None:
        radius = p.crown_diam_m / 2.0 + margin_override
    elif p.exclusion_radius_m is not None:
        radius = p.exclusion_radius_m
    elif p.crown_diam_m is not None:
        radius = p.crown_diam_m / 2.0 + cfg.margin_m
    else:
        radius = cfg.default_radius_m
        warning = RADIUS_DEFAULTED
    clamped = min(max(radius, cfg.radius_min_m), cfg.radius_max_m)
    if clamped != radius:
        warning = RADIUS_CLAMPED
    return (clamped, warning)


def circle_polygon(
    x: float, y: float, r: float, sides: int = 12, circumscribe: bool = True
) -> Polygon:
    """Regular ``sides``-gon, vertex k at angle ``2*pi*k/sides`` from east, counter-clockwise.

    With ``circumscribe`` the vertex radius is ``r / cos(pi / sides)``, so the polygon contains the
    whole circle of radius ``r``.
    """
    if sides < 3:
        raise ValueError(f"sides must be at least 3, got {sides}")
    if not r > 0:
        raise ValueError(f"radius must be positive, got {r!r}")
    vr = r / math.cos(math.pi / sides) if circumscribe else r
    pts = [
        (x + vr * math.cos(2.0 * math.pi * k / sides), y + vr * math.sin(2.0 * math.pi * k / sides))
        for k in range(sides)
    ]
    return Polygon(pts)


def vertex_count(poly: Polygon) -> int:
    """Distinct vertices over the exterior and all interior rings (closing vertices excluded)."""
    return sum(len(r.coords) - 1 for r in (poly.exterior, *poly.interiors))


@dataclass(frozen=True)
class _Edge:
    dist: float
    a: int  # index into the sorted item list; a < b, hence id_a < id_b
    b: int


def _diag(boxes: Sequence[tuple[float, float, float, float]]) -> float:
    minx = min(b[0] for b in boxes)
    miny = min(b[1] for b in boxes)
    maxx = max(b[2] for b in boxes)
    maxy = max(b[3] for b in boxes)
    return math.hypot(maxx - minx, maxy - miny)


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> bool:
        ri, rj = self.find(i), self.find(j)
        if ri == rj:
            return False
        # The smaller index becomes the root, so roots are independent of union order.
        if ri < rj:
            self.parent[rj] = ri
        else:
            self.parent[ri] = rj
        return True


def merge_clusters(
    items: Sequence[tuple[str, Polygon]],
    gap_m: float,
    max_extent_m: float,
    split_report: list[tuple[str, ...]] | None = None,
) -> list[Cluster]:
    """Merge circles whose edges are within ``gap_m`` into connected clusters.

    ``items`` are ``(palm_id, circle polygon)`` in local metres. Two circles are connected when
    ``a.distance(b) <= gap_m``; connected components are clusters. A component's polygon is the
    union of its circles and the convex hull of each pair of circles joined by an edge of the
    minimum spanning tree (Kruskal over the connection graph, weighted by centre distance, ties by
    ``palm_id`` pair), so it is one polygon covering every member circle.

    A component whose bounding-box diagonal exceeds ``max_extent_m`` is split by removing MST edges
    longest first (ties by ``palm_id`` pair) until each part fits. The member ids of every
    component that had to be split are appended to ``split_report`` when it is given (the caller
    reports ``CLUSTER_SPLIT``).

    Returns clusters sorted by first member id. The result does not depend on the order of
    ``items``.
    """
    ordered = sorted(items, key=lambda it: it[0])
    ids = [pid for pid, _ in ordered]
    if len(set(ids)) != len(ids):
        raise GenerationError("duplicate palm_id passed to merge_clusters")
    if not ordered:
        return []
    circles = [poly for _, poly in ordered]
    boxes = [c.bounds for c in circles]
    centres = [(c.centroid.x, c.centroid.y) for c in circles]

    tree = STRtree(circles)
    edges: list[_Edge] = []
    for i, circle in enumerate(circles):
        minx, miny, maxx, maxy = boxes[i]
        window = shapely.box(minx - gap_m, miny - gap_m, maxx + gap_m, maxy + gap_m)
        for j in sorted(int(k) for k in tree.query(window)):
            if j <= i or circle.distance(circles[j]) > gap_m:
                continue
            dist = round(
                math.hypot(centres[i][0] - centres[j][0], centres[i][1] - centres[j][1]),
                _DIST_DECIMALS,
            )
            edges.append(_Edge(dist, i, j))

    # Kruskal: the spanning forest of the connection graph, one tree per component.
    edges.sort(key=lambda e: (e.dist, e.a, e.b))  # index order is palm_id order
    uf = _UnionFind(len(circles))
    tree_edges = [e for e in edges if uf.union(e.a, e.b)]

    components: dict[int, list[int]] = {}
    for i in range(len(circles)):
        components.setdefault(uf.find(i), []).append(i)
    comp_edges: dict[int, list[_Edge]] = {root: [] for root in components}
    for e in tree_edges:
        comp_edges[uf.find(e.a)].append(e)

    clusters: list[Cluster] = []
    for root in sorted(components):
        members = components[root]
        parts = _split_component(members, comp_edges[root], boxes, max_extent_m)
        if len(parts) > 1 and split_report is not None:
            split_report.append(tuple(ids[i] for i in members))
        for part_members, part_edges in parts:
            clusters.append(_build_cluster(part_members, part_edges, ids, circles))
    clusters.sort(key=lambda c: c.member_ids[0])
    return clusters


def _split_component(
    members: list[int],
    edges: list[_Edge],
    boxes: Sequence[tuple[float, float, float, float]],
    max_extent_m: float,
) -> list[tuple[list[int], list[_Edge]]]:
    done: list[tuple[list[int], list[_Edge]]] = []
    stack = [(members, edges)]
    while stack:
        part, part_edges = stack.pop()
        if not part_edges or _diag([boxes[i] for i in part]) <= max_extent_m:
            done.append((part, part_edges))
            continue
        cut = min(part_edges, key=lambda e: (-e.dist, e.a, e.b))
        remaining = [e for e in part_edges if e is not cut]
        uf = _UnionFind(max(part) + 1)
        for e in remaining:
            uf.union(e.a, e.b)
        groups: dict[int, list[int]] = {}
        for i in part:
            groups.setdefault(uf.find(i), []).append(i)
        group_edges: dict[int, list[_Edge]] = {root: [] for root in groups}
        for e in remaining:
            group_edges[uf.find(e.a)].append(e)
        for root, group in groups.items():
            stack.append((group, group_edges[root]))
    return done


def _build_cluster(
    members: list[int], edges: list[_Edge], ids: list[str], circles: list[Polygon]
) -> Cluster:
    member_ids = tuple(ids[i] for i in sorted(members))
    if len(members) == 1:
        return Cluster(member_ids, circles[members[0]])
    parts: list[Any] = [circles[i] for i in sorted(members)]
    for e in sorted(edges, key=lambda e: (e.a, e.b)):
        parts.append(unary_union([circles[e.a], circles[e.b]]).convex_hull)
    merged = unary_union(parts)
    if not isinstance(merged, Polygon) or merged.is_empty or not merged.is_valid:
        raise GenerationError(f"cluster {member_ids[0]}: merging circles gave an invalid polygon")
    return Cluster(member_ids, merged)


def simplify_cluster(poly: Polygon, tol_m: float, max_vertices: int) -> tuple[Polygon, bool]:
    """Simplify with ``tol_m`` (topology preserved), doubling it while over ``max_vertices``.

    Returns ``(polygon, simplified_flag)``; the flag is True when the vertex limit forced the
    tolerance above ``tol_m`` (the caller reports ``VERTICES_SIMPLIFIED``). Raises
    ``GenerationError`` when the polygon is still over the limit after 5 doublings.
    """
    tol = tol_m
    out = _simplify(poly, tol)
    doublings = 0
    while vertex_count(out) > max_vertices:
        if doublings == _MAX_DOUBLINGS:
            raise GenerationError(
                f"polygon still has {vertex_count(out)} vertices (limit {max_vertices}) "
                f"after simplifying with tolerance {tol} m"
            )
        tol *= 2.0
        doublings += 1
        out = _simplify(poly, tol)
    return (out, doublings > 0)


def _simplify(poly: Polygon, tol: float) -> Polygon:
    out = poly.simplify(tol, preserve_topology=True)
    if not isinstance(out, Polygon) or out.is_empty or not out.is_valid:
        raise GenerationError(f"simplifying with tolerance {tol} m gave an invalid polygon")
    return out


def normalize_ring(
    poly_lonlat: Polygon, orientation: str, decimals: int, closed: bool
) -> tuple[tuple[float, float], ...]:
    """Canonical exterior ring of a lon/lat polygon, as ``(lon, lat)`` tuples.

    Coordinates are rounded to ``decimals``, consecutive duplicates dropped, the ring oriented
    (``"ccw"`` or ``"cw"``) and rotated to start at its smallest ``(lon, lat)`` vertex. The
    closing vertex is appended only when ``closed``. Interior rings are an error: remove holes
    first.
    """
    if orientation not in ("ccw", "cw"):
        raise ValueError(f"orientation must be 'ccw' or 'cw', got {orientation!r}")
    if len(poly_lonlat.interiors) > 0:
        raise GenerationError("normalize_ring needs a polygon without holes")
    pts: list[tuple[float, float]] = []
    for lon, lat in poly_lonlat.exterior.coords:
        pt = (round(lon, decimals) + 0.0, round(lat, decimals) + 0.0)  # + 0.0 turns -0.0 into 0.0
        if not pts or pts[-1] != pt:
            pts.append(pt)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    if len(pts) < 3:
        raise GenerationError(f"ring has {len(pts)} distinct vertices after rounding to {decimals}")
    n = len(pts)
    area2 = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))
    if area2 == 0:
        raise GenerationError(f"ring is degenerate after rounding to {decimals} decimals")
    if (area2 > 0) != (orientation == "ccw"):
        pts.reverse()
    start = pts.index(min(pts))
    pts = pts[start:] + pts[:start]
    if closed:
        pts.append(pts[0])
    return tuple(pts)
