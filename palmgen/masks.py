"""Mod and airport masks, and the Overpass airport fetch.

Masks come from three places, in this order: the region's ``mask_out`` entries (inline ``bbox``,
inline ``geometry`` or a GeoJSON ``path``), then one mask per feature of the airport file
(``masks.airports.path``) unless disabled. Order matters: a palm inside two masks is reported under
the first one.

Airport polygons are stored unbuffered; this module buffers them by ``masks.airports.buffer_m``
in a local metric projection (``palmgen.geometry.LocalProjection``), so the result is the same on
every run. A manual ``mask_out`` entry of kind ``airport`` is used as drawn (not buffered).

Paths in :class:`~palmgen.inputs.GenConfig` are already absolute (ARCH-003); nothing here resolves
them.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import shapely
from shapely import STRtree, make_valid
from shapely.geometry import MultiPolygon, Polygon, box, shape
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import linemerge, polygonize, unary_union

from palmcore.config import MaskArea
from palmcore.geo import Bbox
from palmcore.log import get_logger
from palmgen.errors import GenerationError, InputError
from palmgen.geometry import LocalProjection, remove_holes
from palmgen.inputs import GenConfig, load_gen_config
from palmgen.model import Palm

log = get_logger(__name__)

AIRPORT_KINDS: Final = frozenset({"airport"})
USER_AGENT: Final = "palmgen"
HTTP_TIMEOUT_S: Final = 90
RETRY_STATUSES: Final = frozenset({429, 502, 504})
MAX_ATTEMPTS: Final = 4
BACKOFF_BASE_S: Final = 5.0
ATTRIBUTION: Final = (
    "Aerodrome boundaries (c) OpenStreetMap contributors, ODbL 1.0, "
    "https://www.openstreetmap.org/copyright"
)
_BUFFER_QUAD_SEGS: Final = 8
_COORD_PRECISION: Final = 1e-7
_AIRPORT_HINT: Final = (
    "use the RISK-004 file docs/compat/airports-mask.geojson, run "
    "`palmgen masks airports --region NAME --out <path>` and point masks.airports.path at it, "
    "or set masks.airports.enabled: false (or pass --no-airport-mask)"
)

# POST function: (url, body) -> response bytes. Raises OverpassHttpError on an HTTP error status.
HttpPost = Callable[[str, bytes], bytes]


@dataclass(frozen=True)
class Mask:
    """A named exclusion area in lon/lat. ``kind`` is ``mod``, ``airport`` or ``other``."""

    name: str
    kind: str
    geometry_lonlat: BaseGeometry


@dataclass(frozen=True)
class LocalMask:
    """A mask in local metres (see :func:`localize_masks`)."""

    name: str
    kind: str
    geometry: BaseGeometry


class OverpassHttpError(Exception):
    """An HTTP error status from the Overpass endpoint."""

    def __init__(self, status: int, message: str = "") -> None:
        super().__init__(f"HTTP {status}{': ' + message if message else ''}")
        self.status = status


# --------------------------------------------------------------------------- loading


def _polygon_parts(g: BaseGeometry) -> list[Polygon]:
    """Non-empty Polygons in ``g``; lines, points and empty parts are discarded."""
    out: list[Polygon] = []
    for part in shapely.get_parts(g):
        if isinstance(part, Polygon):
            if not part.is_empty:
                out.append(part)
        elif part.geom_type == "GeometryCollection":
            out.extend(_polygon_parts(part))
    return out


def _polygonal(geom: BaseGeometry) -> BaseGeometry | None:
    """Polygon or MultiPolygon part of ``geom`` (repaired), or None when it has none."""
    if geom.is_empty:
        return None
    parts = _polygon_parts(geom if geom.is_valid else make_valid(geom))
    if not parts:
        return None
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def _geometries_in(doc: Any) -> list[Mapping[str, Any]]:
    """GeoJSON geometry objects in a FeatureCollection, Feature or bare geometry."""
    if not isinstance(doc, Mapping):
        return []
    kind = doc.get("type")
    if kind == "FeatureCollection":
        feats = doc.get("features")
        out: list[Mapping[str, Any]] = []
        for f in feats if isinstance(feats, list) else []:
            out.extend(_geometries_in(f))
        return out
    if kind == "Feature":
        geom = doc.get("geometry")
        return [geom] if isinstance(geom, Mapping) else []
    if kind == "GeometryCollection":
        geoms = doc.get("geometries")
        return [g for g in geoms if isinstance(g, Mapping)] if isinstance(geoms, list) else []
    return [doc] if "coordinates" in doc else []


def _read_geojson(path: Path, what: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(f"cannot read {what} {path}: {exc}") from exc
    except ValueError as exc:
        raise InputError(f"{what} {path} is not valid JSON: {exc}") from exc


def _to_shape(geometry: Mapping[str, Any], where: str) -> BaseGeometry | None:
    try:
        return _polygonal(shape(geometry))
    except (ValueError, TypeError, KeyError, shapely.errors.ShapelyError) as exc:
        raise InputError(f"{where}: bad geometry: {exc}") from exc


def _mask_area_geometry(area: MaskArea) -> BaseGeometry:
    pieces: list[BaseGeometry] = []
    if area.bbox is not None:
        pieces.append(box(*area.bbox.as_tuple()))
    if area.geometry is not None:
        geom = _to_shape(area.geometry, f"mask {area.name!r} geometry")
        if geom is not None:
            pieces.append(geom)
    if area.path is not None:
        if not area.path.is_file():
            raise InputError(f"mask {area.name!r}: file not found: {area.path}")
        doc = _read_geojson(area.path, f"mask {area.name!r} file")
        for i, g in enumerate(_geometries_in(doc)):
            geom = _to_shape(g, f"mask {area.name!r} file {area.path} geometry {i}")
            if geom is not None:
                pieces.append(geom)
    if not pieces:
        raise InputError(f"mask {area.name!r} has no polygon area (bbox, geometry or path)")
    merged = unary_union(pieces)
    return _polygonal(merged) or Polygon()


def _unique(name: str, taken: set[str]) -> str:
    out = name
    n = 2
    while out in taken:
        out = f"{name}#{n}"
        n += 1
    taken.add(out)
    return out


def _airport_name(props: Mapping[str, Any], index: int) -> str:
    for key in ("code", "icao", "faa", "osm_id", "name"):
        value = props.get(key)
        if isinstance(value, str) and value:
            return f"airport:{value}"
    return f"airport:#{index}"


def _load_airport_masks(
    path: Path, buffer_m: float, projection: LocalProjection, taken: set[str]
) -> list[Mask]:
    if not path.is_file():
        raise InputError(f"airport mask file not found: {path}. Fix: {_AIRPORT_HINT}")
    doc = _read_geojson(path, "airport mask file")
    feats = doc.get("features") if isinstance(doc, Mapping) else None
    if not isinstance(feats, list):
        raise InputError(f"airport mask file {path}: expected a GeoJSON FeatureCollection")
    out: list[Mask] = []
    for i, feat in enumerate(feats):
        props = feat.get("properties") if isinstance(feat, Mapping) else None
        geoms = _geometries_in(feat)
        shapes = [s for g in geoms if (s := _to_shape(g, f"{path} feature {i}")) is not None]
        if not shapes:
            log.warning("%s: feature %d has no polygon geometry, skipped", path, i)
            continue
        geom = unary_union(shapes)
        if buffer_m > 0:
            local = projection.geom_to_local(geom)
            geom = projection.geom_to_lonlat(local.buffer(buffer_m, quad_segs=_BUFFER_QUAD_SEGS))
        name = _unique(_airport_name(props if isinstance(props, Mapping) else {}, i), taken)
        out.append(Mask(name, "airport", geom))
    return out


def load_masks(
    cfg: GenConfig, projection: LocalProjection, no_airport_mask: bool = False
) -> list[Mask]:
    """All masks for a build, in config order, then the airport file's features.

    ``mask_out`` entries are returned as drawn. The airport file ``cfg.airports.path`` is read
    when ``cfg.airports.enabled`` and not ``no_airport_mask``; each feature becomes a mask named
    ``airport:<code>`` buffered by ``cfg.airports.buffer_m`` metres in ``projection``. A missing
    airport file raises :class:`InputError` with a hint.
    """
    taken: set[str] = {m.name for m in cfg.mask_out}
    masks = [Mask(m.name, m.kind, _mask_area_geometry(m)) for m in cfg.mask_out]
    if cfg.airports.enabled and not no_airport_mask:
        if cfg.airports.path is None:
            raise InputError(f"masks.airports.path is not set. Fix: {_AIRPORT_HINT}")
        masks.extend(
            _load_airport_masks(cfg.airports.path, cfg.airports.buffer_m, projection, taken)
        )
    return masks


def localize_masks(masks: Iterable[Mask], projection: LocalProjection) -> list[LocalMask]:
    """The same masks with geometry in local metres, for :func:`clip_polygons_by_masks`."""
    return [LocalMask(m.name, m.kind, projection.geom_to_local(m.geometry_lonlat)) for m in masks]


# --------------------------------------------------------------------------- applying


def apply_point_masks(
    palms: Sequence[Palm], masks: Sequence[Mask]
) -> tuple[list[Palm], dict[str, list[str]]]:
    """Drop palms inside any mask (boundary counts as inside).

    Returns the kept palms in input order and ``{mask_name: [palm_ids]}`` (sorted ids) with an
    entry for every mask, in mask order. A palm inside several masks is listed under the first.
    """
    dropped: dict[str, list[str]] = {m.name: [] for m in masks}
    if not palms or not masks:
        return list(palms), dropped
    xs = np.array([p.lon for p in palms], dtype=float)
    ys = np.array([p.lat for p in palms], dtype=float)
    free = np.ones(len(palms), dtype=bool)
    for mask in masks:
        hit = np.zeros(len(palms), dtype=bool)
        hit[free] = shapely.intersects_xy(mask.geometry_lonlat, xs[free], ys[free])
        free &= ~hit
        dropped[mask.name] = sorted(palms[int(i)].palm_id for i in np.flatnonzero(hit))
    kept = [p for p, keep in zip(palms, free, strict=True) if keep]
    return kept, dropped


def clip_polygons_by_masks(
    polys_local: Sequence[Polygon],
    masks_local: Sequence[LocalMask],
    kinds: Collection[str] = AIRPORT_KINDS,
    *,
    min_part_area_m2: float = 1.0,
    supports_holes: bool = False,
) -> tuple[list[tuple[int, Polygon]], dict[str, int]]:
    """Subtract the masks of the given ``kinds`` from each polygon.

    Returns ``(parts, clipped)``. ``parts`` is ``(index into polys_local, polygon)`` for every
    surviving piece, in input order, pieces of one polygon sorted by ``(minx, miny)``; an
    untouched polygon comes back as is, a polygon removed entirely has no entry. Holes are split
    out (``remove_holes``) unless ``supports_holes``; pieces under ``min_part_area_m2`` are
    dropped. ``clipped`` has an entry for every mask of the selected kinds (mask order) counting
    the polygons it cut (touching without overlap does not count). Masks apply in order, so a
    polygon cut by two masks counts for both.
    """
    chosen = [m for m in masks_local if m.kind in kinds]
    clipped: dict[str, int] = {m.name: 0 for m in chosen}
    tree = STRtree([m.geometry for m in chosen]) if chosen else None
    out: list[tuple[int, Polygon]] = []
    for i, poly in enumerate(polys_local):
        hits = sorted(int(j) for j in tree.query(poly, predicate="intersects")) if tree else []
        pieces: list[Polygon] = [poly]
        cut = False
        for j in hits:
            mask = chosen[j]
            nxt: list[Polygon] = []
            touched = False
            for piece in pieces:
                if piece.intersection(mask.geometry).area > 0.0:
                    touched = True
                    nxt.extend(_polygon_parts(make_valid(piece.difference(mask.geometry))))
                else:
                    nxt.append(piece)
            if touched:
                clipped[mask.name] += 1
                cut = True
            pieces = nxt
        if not cut:
            out.append((i, poly))
            continue
        if not supports_holes:
            pieces = [q for p in pieces for q in remove_holes(p)]
        kept = [p for p in pieces if p.area >= min_part_area_m2]
        kept.sort(key=lambda p: (p.bounds[0], p.bounds[1], p.wkb_hex))
        out.extend((i, p) for p in kept)
    return out, clipped


# --------------------------------------------------------------------------- Overpass


def _ring_points(geometry: Any) -> list[tuple[float, float]]:
    return [(float(p["lon"]), float(p["lat"])) for p in geometry or []]


def _finish(geom: BaseGeometry) -> BaseGeometry | None:
    geom = _polygonal(shapely.set_precision(geom, _COORD_PRECISION))
    if geom is None:
        return None
    if isinstance(geom, MultiPolygon):
        geom = MultiPolygon(sorted((orient(p) for p in geom.geoms), key=lambda p: p.bounds))
    else:
        geom = orient(geom)
    return geom


def _lists(value: Any) -> Any:
    return [_lists(v) for v in value] if isinstance(value, (list, tuple)) else value


def _geojson(geom: BaseGeometry) -> dict[str, Any]:
    m = shapely.geometry.mapping(geom)
    return {"type": m["type"], "coordinates": _lists(m["coordinates"])}


def _way_polygon(element: Mapping[str, Any]) -> BaseGeometry | None:
    pts = _ring_points(element.get("geometry"))
    if len(pts) < 4 or pts[0] != pts[-1]:
        return None
    return Polygon(pts)


def _relation_polygon(element: Mapping[str, Any]) -> BaseGeometry | None:
    outers: list[Any] = []
    inners: list[Any] = []
    for member in element.get("members") or []:
        if member.get("type") != "way":
            continue
        pts = _ring_points(member.get("geometry"))
        if len(pts) < 2:
            continue
        line = shapely.LineString(pts)
        (inners if member.get("role") == "inner" else outers).append(line)
    if not outers:
        return None
    outer_polys = list(polygonize(linemerge(outers)))
    if not outer_polys:
        return None
    result = unary_union(outer_polys)
    if inners:
        holes = list(polygonize(linemerge(inners)))
        if holes:
            result = result.difference(unary_union(holes))
    return result


def overpass_to_geojson(resp: Mapping[str, Any]) -> dict[str, Any]:
    """Convert an Overpass ``out geom`` JSON response to a GeoJSON FeatureCollection.

    Closed ways become Polygons; relations have their outer members merged and polygonized
    (inner members cut holes) and become Polygons or MultiPolygons. Open ways, relations that do
    not close and elements without geometry are skipped with a warning. Features carry
    ``name``, ``icao`` (null when untagged) and ``osm_id`` (``way/<id>`` or ``relation/<id>``),
    sorted ways first then relations by id; exteriors are counter-clockwise and coordinates are
    snapped to 1e-7 degrees, so the result is deterministic. The ``attribution`` member credits
    OpenStreetMap (ODbL).
    """
    elements = resp.get("elements")
    if not isinstance(elements, list):
        raise GenerationError("Overpass response has no 'elements' list")
    features: list[tuple[int, int, dict[str, Any]]] = []
    for el in elements:
        kind = el.get("type")
        if kind not in ("way", "relation"):
            continue
        osm_id = f"{kind}/{el.get('id')}"
        raw = _way_polygon(el) if kind == "way" else _relation_polygon(el)
        geom = None if raw is None else _finish(raw)
        if geom is None:
            log.warning("Overpass %s skipped: no closed polygon", osm_id)
            continue
        tags = el.get("tags") or {}
        features.append(
            (
                0 if kind == "way" else 1,
                int(el.get("id", 0)),
                {
                    "type": "Feature",
                    "properties": {
                        "name": tags.get("name"),
                        "icao": tags.get("icao"),
                        "osm_id": osm_id,
                    },
                    "geometry": _geojson(geom),
                },
            )
        )
    features.sort(key=lambda t: (t[0], t[1]))
    return {
        "type": "FeatureCollection",
        "name": "airports",
        "attribution": ATTRIBUTION,
        "features": [f for _, _, f in features],
    }


def overpass_query(bbox: Bbox) -> str:
    """The Overpass QL query for aerodrome ways and relations inside ``bbox`` (S,W,N,E)."""
    s, w, n, e = bbox.lat_min, bbox.lon_min, bbox.lat_max, bbox.lon_max
    area = f"({s:.7f},{w:.7f},{n:.7f},{e:.7f})"
    return (
        "[out:json][timeout:60];("
        f'way["aeroway"="aerodrome"]{area};relation["aeroway"="aerodrome"]{area};'
        ");out geom;"
    )


def _urllib_post(url: str, body: bytes) -> bytes:
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as resp:
            data: bytes = resp.read()
            return data
    except urllib.error.HTTPError as exc:
        raise OverpassHttpError(exc.code, str(exc.reason)) from exc


def fetch_airports(
    bbox: Bbox,
    out_path: Path,
    endpoint: str,
    http_post: HttpPost | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Fetch aerodrome polygons in ``bbox`` from Overpass, write them to ``out_path``.

    ``http_post(url, body)`` returns the response bytes; the default uses ``urllib`` with a 90 s
    timeout and the User-Agent ``palmgen``. HTTP 429, 502 and 504 are retried up to 4 attempts
    with 5, 10, 20 s waits (``sleep``); other failures raise :class:`GenerationError`. An Overpass
    ``remark`` (for example a runtime error) also fails: the data may be partial. Returns the
    number of features written.
    """
    post = http_post if http_post is not None else _urllib_post
    body = urllib.parse.urlencode({"data": overpass_query(bbox)}).encode("ascii")
    payload: bytes | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            payload = post(endpoint, body)
            break
        except OverpassHttpError as exc:
            if exc.status not in RETRY_STATUSES or attempt == MAX_ATTEMPTS - 1:
                raise GenerationError(f"Overpass request to {endpoint} failed: {exc}") from exc
            wait = BACKOFF_BASE_S * 2**attempt
            log.warning("Overpass %s, retrying in %.0f s", exc, wait)
            sleep(wait)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GenerationError(f"Overpass request to {endpoint} failed: {exc}") from exc
    assert payload is not None  # the loop either breaks with a payload or raises
    try:
        resp = json.loads(payload)
    except ValueError as exc:
        raise GenerationError(f"Overpass response is not JSON: {exc}") from exc
    if not isinstance(resp, dict):
        raise GenerationError("Overpass response is not a JSON object")
    remark = resp.get("remark")
    if remark:
        raise GenerationError(f"Overpass reported a problem (data may be incomplete): {remark}")
    doc = overpass_to_geojson(resp)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.name + ".tmp")
    tmp.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    os.replace(tmp, out_path)
    return len(doc["features"])


def run_fetch_airports(opts: Any) -> int:
    """``palmgen masks airports``: fetch aerodromes for the region bbox into ``opts.out``.

    The query box is the region bbox grown by ``masks.airports.buffer_m``. ``opts.http_post`` may
    carry an injected HTTP function (tests); the CLI never sets it.
    """
    cfg = load_gen_config(opts.region, Path(opts.config))
    bbox = cfg.bbox.buffer_m(cfg.airports.buffer_m)
    count = fetch_airports(bbox, Path(opts.out), opts.endpoint, getattr(opts, "http_post", None))
    if count == 0:
        log.warning("no aerodromes found in %s", bbox.to_list())
    print(f"wrote {count} airport polygons to {opts.out}")
    return 0
