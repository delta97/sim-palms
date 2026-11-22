"""Building footprint adapter: OSM (Overpass) or a local Microsoft footprints file.

``fetch_buildings(cfg, cache, http)`` returns ``(GeoDataFrame, warnings)``. The frame has the
columns ``building_id``, ``source`` and ``geometry`` (Polygon/MultiPolygon, EPSG:4326), all
geometries valid and non-empty, sorted by ``building_id``. The rows satisfy the
``buildings.geojson`` contract (``palmcore.contract.validate_buildings``).

Licences (``docs/licenses/data-sources.md``): OSM is ODbL 1.0, copyright OpenStreetMap
contributors; Microsoft Global ML Building Footprints are CDLA Permissive 2.0. The ``source``
column names the origin; the notices are in :data:`SOURCE_NOTICES` and in
``frame.attrs["attribution"]`` / ``frame.attrs["license"]`` (``attrs`` does not survive every
pandas operation, so writers should look the notice up from ``source``).

Which source a region uses is a configuration choice (DEC-009); this module supports both.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import pyproj
import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from palmcore.log import get_logger
from palmscan.cache import Cache
from palmscan.geo import WGS84
from palmscan.http import HttpClient
from palmscan.sources.base import SourceError
from palmscan.sources.overpass import OSM_ATTRIBUTION, OSM_LICENSE, OverpassClient

if TYPE_CHECKING:
    import geopandas as gpd

    from palmscan.config import ScanConfig

__all__ = [
    "BUILDINGS_QUERY",
    "MICROSOFT_ATTRIBUTION",
    "MICROSOFT_LICENSE",
    "NO_BUILDINGS_WARNING",
    "SOURCE_NOTICES",
    "fetch_buildings",
]

_log = get_logger(__name__)

BUILDINGS_QUERY: Final = """[out:json][timeout:180];
(way["building"]({south},{west},{north},{east});
relation["building"]["type"="multipolygon"]({south},{west},{north},{east}););
out geom;"""

MICROSOFT_LICENSE: Final = "CDLA-Permissive-2.0"
MICROSOFT_ATTRIBUTION: Final = "Microsoft Global ML Building Footprints"
NO_BUILDINGS_WARNING: Final = "no building footprints; building_conflict is false everywhere"
SOURCE_OSM: Final = "osm"
SOURCE_MICROSOFT: Final = "microsoft_footprints"
SOURCE_NOTICES: Final[dict[str, dict[str, str]]] = {
    SOURCE_OSM: {"license": OSM_LICENSE, "attribution": OSM_ATTRIBUTION},
    SOURCE_MICROSOFT: {"license": MICROSOFT_LICENSE, "attribution": MICROSOFT_ATTRIBUTION},
}
_COLUMNS: Final = ["building_id", "source", "geometry"]


# ------------------------------------------------------------------------- geometry helpers


def _polygons(geom: BaseGeometry | None) -> list[Polygon]:
    """Non-empty polygons inside ``geom``; lines, points and empty parts are dropped."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom]
    if hasattr(geom, "geoms"):
        return [p for part in geom.geoms for p in _polygons(part)]
    return []


def _repair(geom: BaseGeometry | None) -> tuple[Polygon | MultiPolygon | None, bool]:
    """Valid, non-empty Polygon/MultiPolygon for ``geom`` (or ``None``) and a repaired flag."""
    if geom is None or geom.is_empty:
        return None, False
    repaired = not geom.is_valid
    fixed = shapely.make_valid(geom) if repaired else geom
    parts = [p for p in _polygons(fixed) if p.area > 0.0]
    if not parts:
        return None, repaired
    return (parts[0] if len(parts) == 1 else MultiPolygon(parts)), repaired


def _empty_frame() -> gpd.GeoDataFrame:
    import geopandas as gpd

    return gpd.GeoDataFrame(
        {"building_id": [], "source": []}, geometry=gpd.GeoSeries([], crs=WGS84), crs=WGS84
    )[_COLUMNS]


def _frame(rows: list[tuple[str, BaseGeometry]], source: str) -> gpd.GeoDataFrame:
    import geopandas as gpd

    if not rows:
        frame = _empty_frame()
    else:
        rows = sorted(rows, key=lambda r: r[0])
        frame = gpd.GeoDataFrame(
            {"building_id": [r[0] for r in rows], "source": [source] * len(rows)},
            geometry=[r[1] for r in rows],
            crs=WGS84,
        )[_COLUMNS]
    frame.attrs.update(SOURCE_NOTICES.get(source, {}))
    return frame


# --------------------------------------------------------------------------------- OSM


def _line(points: Any) -> LineString | None:
    """LineString from an Overpass ``geometry`` list (``[{lat, lon}, ...]``)."""
    if not isinstance(points, list):
        return None
    try:
        coords = [(float(p["lon"]), float(p["lat"])) for p in points]
    except (KeyError, TypeError, ValueError):
        return None
    return LineString(coords) if len(coords) >= 2 else None


def _closed_ring_polygon(line: LineString | None) -> Polygon | None:
    if line is None or len(line.coords) < 4 or not line.is_closed:
        return None
    return Polygon(line.coords)


def _relation_polygon(element: dict[str, Any]) -> BaseGeometry | None:
    """Assemble a multipolygon relation: outer rings minus inner rings, or ``None``.

    Member ways with an empty role count as outer. Rings are formed by noding all member
    segments of a role and polygonizing, so an outer ring split over several ways is joined.
    An outer member without inline geometry (it lies outside the query box) makes the ring
    unassemblable: the relation is then ``None`` rather than a wrong shape.
    """
    outer: list[LineString] = []
    inner: list[LineString] = []
    for member in element.get("members") or []:
        if not isinstance(member, dict) or member.get("type") != "way":
            continue
        role = member.get("role") or "outer"
        if role not in ("outer", "inner"):
            continue
        line = _line(member.get("geometry"))
        if line is None:
            if role == "outer":
                return None
            continue
        (outer if role == "outer" else inner).append(line)
    if not outer:
        return None
    outer_polys = list(polygonize(unary_union(outer)))
    if not outer_polys:
        return None
    shape: BaseGeometry = unary_union(outer_polys)
    if inner:
        inner_polys = list(polygonize(unary_union(inner)))
        if inner_polys:
            shape = shape.difference(unary_union(inner_polys))
    return shape


def _osm_buildings(
    cfg: ScanConfig, cache: Cache, http: HttpClient
) -> tuple[gpd.GeoDataFrame, list[str]]:
    bbox = cfg.bbox
    client = OverpassClient(http, cache, cfg.region.sources.overpass_url)
    body = client.query_bbox(BUILDINGS_QUERY, bbox)
    window = box(bbox.lon_min, bbox.lat_min, bbox.lon_max, bbox.lat_max)

    rows: dict[str, BaseGeometry] = {}
    unclosed = unassembled = repaired_n = empty_after_repair = 0
    for element in body.get("elements") or []:
        if not isinstance(element, dict):
            continue
        kind, eid = element.get("type"), element.get("id")
        if eid is None:
            continue
        if kind == "way":
            if not (element.get("tags") or {}).get("building"):
                continue
            raw: BaseGeometry | None = _closed_ring_polygon(_line(element.get("geometry")))
            if raw is None:
                unclosed += 1
                continue
        elif kind == "relation":
            raw = _relation_polygon(element)
            if raw is None:
                unassembled += 1
                continue
        else:
            continue
        geom, repaired = _repair(raw)
        if geom is None:
            empty_after_repair += 1
            continue
        repaired_n += int(repaired)
        if not geom.intersects(window):
            continue
        rows[f"{kind}/{eid}"] = geom

    warnings: list[str] = []
    if unclosed:
        warnings.append(f"osm buildings: {unclosed} unclosed or degenerate ways skipped")
    if unassembled:
        warnings.append(
            f"osm buildings: {unassembled} multipolygon relations skipped "
            "(rings could not be assembled)"
        )
    if empty_after_repair:
        warnings.append(
            f"osm buildings: {empty_after_repair} geometries empty after repair, skipped"
        )
    if repaired_n:
        warnings.append(f"osm buildings: {repaired_n} invalid geometries repaired")
    return _frame(list(rows.items()), SOURCE_OSM), warnings


# ----------------------------------------------------------------------------- Microsoft


def _microsoft_buildings(cfg: ScanConfig) -> tuple[gpd.GeoDataFrame, list[str]]:
    import geopandas as gpd
    import pyogrio

    path = cfg.region.sources.buildings_path
    if path is None:
        raise SourceError(
            "sources.buildings is 'microsoft_footprints' but sources.buildings_path is not set"
        )
    path = Path(path)
    if not path.is_file():
        raise SourceError(f"building footprints file not found: {path}")
    try:
        info = pyogrio.read_info(path)
    except Exception as exc:
        raise SourceError(f"cannot read building footprints {path.name}: {exc}") from exc

    warnings: list[str] = []
    bbox = cfg.bbox
    read_box: tuple[float, float, float, float] = (
        bbox.lon_min,
        bbox.lat_min,
        bbox.lon_max,
        bbox.lat_max,
    )
    wgs84 = pyproj.CRS.from_user_input(WGS84)
    file_crs = pyproj.CRS.from_user_input(info["crs"]) if info.get("crs") else None
    reproject = file_crs is not None and file_crs != wgs84
    if reproject and file_crs is not None:
        to_file = pyproj.Transformer.from_crs(wgs84, file_crs, always_xy=True)
        xmin, ymin, xmax, ymax = to_file.transform_bounds(*read_box, densify_pts=21)
        read_box = (xmin, ymin, xmax, ymax)
        warnings.append(f"building file CRS is {file_crs.to_string()}: reprojected to WGS84")
    try:
        frame = gpd.read_file(path, bbox=read_box, engine="pyogrio", fid_as_index=True)
    except Exception as exc:
        raise SourceError(f"cannot read building footprints {path.name}: {exc}") from exc
    if reproject:
        frame = frame.to_crs(WGS84)

    rows: list[tuple[str, BaseGeometry]] = []
    repaired_n = dropped = 0
    for fid, raw in zip(frame.index, frame.geometry, strict=True):
        geom, repaired = _repair(raw)
        if geom is None:
            dropped += 1
            continue
        repaired_n += int(repaired)
        rows.append((f"msbf:{fid}", geom))
    if dropped:
        warnings.append(f"microsoft footprints: {dropped} empty or non-polygon rows skipped")
    if repaired_n:
        warnings.append(f"microsoft footprints: {repaired_n} invalid geometries repaired")
    return _frame(rows, SOURCE_MICROSOFT), warnings


# ----------------------------------------------------------------------------- entry point


def fetch_buildings(
    cfg: ScanConfig, cache: Cache, http: HttpClient
) -> tuple[gpd.GeoDataFrame, list[str]]:
    """Building footprints for ``cfg.bbox`` from the source named by ``sources.buildings``.

    ``osm`` queries Overpass (cached); ``microsoft_footprints`` reads the local file at
    ``sources.buildings_path`` (GeoJSON, GeoJSON lines or GPKG; ids ``msbf:<feature id>``, the
    0-based row for GeoJSON and GeoJSON lines, the fid for GPKG); ``none`` returns an empty
    frame and a warning. Raises :class:`SourceError` for an unknown type or an unusable file.
    """
    kind = cfg.region.sources.buildings.type
    if kind in ("none", None):
        return _empty_frame(), [NO_BUILDINGS_WARNING]
    if kind == SOURCE_OSM:
        frame, warnings = _osm_buildings(cfg, cache, http)
    elif kind == SOURCE_MICROSOFT:
        frame, warnings = _microsoft_buildings(cfg)
    else:
        raise SourceError(f"unknown buildings source {kind!r} (osm, microsoft_footprints, none)")
    for message in warnings:
        _log.warning("%s", message)
    _log.info("buildings: %d footprints from %s", len(frame), kind)
    return frame, warnings
