"""``qa_map.gpkg``: layers for reviewing a run in QGIS over aerial imagery (plan W10).

Layers are written in EPSG:4326. Buffers are built in the local metric CRS first. Empty layers
are still written, with their schema, so QGIS projects that reference them keep working.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import geopandas as gpd
import pandas as pd
import pyproj
from shapely.geometry import Point, box
from shapely.geometry.base import BaseGeometry

from palmscan import geo
from palmscan.model import LidarCandidate, PalmRecord, Reject
from palmscan.output import assign_palm_ids, stable_key_for
from palmscan.qa.rejects import METRIC_COLUMNS, sorted_rejects

__all__ = [
    "CHECK_RADIUS_M",
    "LAYER_NAMES",
    "ConflictBuilding",
    "vintage_cell_id",
    "vintage_grid",
    "write_qa_gpkg",
]

CHECK_RADIUS_M: Final = 3.0
DEFAULT_ID_PREFIX: Final = "pal"
_QUAD_SEGS: Final = 16
_WGS84: Final = "EPSG:4326"

LAYER_NAMES: Final = (
    "palms",
    "exclusion_circles",
    "check_radius_3m",
    "rejects",
    "building_conflicts",
    "vintage_grid",
)
CANDIDATES_LAYER: Final = "lidar_candidates"
CROWNS_LAYER: Final = "crowns"

Columns = dict[str, tuple[str, list[Any]]]


@dataclass(frozen=True, slots=True)
class ConflictBuilding:
    """A building footprint that conflicts with a palm exclusion circle (geometry in WGS84)."""

    building_id: str
    source: str
    geometry: BaseGeometry


# ---------------------------------------------------------------------------------------------
# Vintage grid


def _decimals(step_deg: float) -> int:
    return max(0, math.ceil(-math.log10(step_deg) - 1e-9))


def _cell_index(value: float, step_deg: float) -> int:
    return math.floor(value / step_deg + 1e-9)


def _axis_label(index: int, step_deg: float, decimals: int, pos: str, neg: str) -> str:
    scale = 10**decimals
    scaled = round(index * step_deg * scale)
    whole, frac = divmod(abs(scaled), scale)
    label = f"{whole}p{frac:0{decimals}d}" if decimals else str(whole)
    return (neg if scaled < 0 else pos) + label


def _cell_label(ix: int, iy: int, step_deg: float) -> str:
    decimals = _decimals(step_deg)
    lat = _axis_label(iy, step_deg, decimals, "n", "s")
    lon = _axis_label(ix, step_deg, decimals, "e", "w")
    return f"{lat}_{lon}"


def vintage_cell_id(lon: float, lat: float, step_deg: float) -> str:
    """Cell id of the grid cell holding the point, e.g. ``n32p78_w117p26``.

    Cells are aligned to multiples of ``step_deg``; the id names the south-west corner.
    """
    return _cell_label(_cell_index(lon, step_deg), _cell_index(lat, step_deg), step_deg)


def _year(text: str) -> int | None:
    head = text.strip()[:4]
    return int(head) if len(head) == 4 and head.isdigit() else None


def _palm_years(palm: PalmRecord) -> tuple[list[int], list[int]]:
    """Vintage years of one palm as ``(inventory, lidar)``.

    A ``data_vintage`` key starting with ``lidar`` is LiDAR; every other key is inventory (or
    OSM). The vintage of the palm's LiDAR candidate counts as LiDAR when no such key exists.
    """
    inventory: list[int] = []
    lidar: list[int] = []
    for key, value in palm.data_vintage.items():
        year = _year(value)
        if year is not None:
            (lidar if key.startswith("lidar") else inventory).append(year)
    if palm.lidar is not None and palm.lidar.vintage and not lidar:
        year = _year(palm.lidar.vintage)
        if year is not None:
            lidar.append(year)
    return inventory, lidar


def _median(values: list[int]) -> float | None:
    return float(statistics.median(values)) if values else None


_GRID_COLUMNS: Final = (
    "cell_id",
    "palm_count",
    "inventory_vintage",
    "lidar_vintage",
    "stale",
    "geometry",
)


def vintage_grid(
    palms: Iterable[PalmRecord],
    step_deg: float,
    run_year: int,
    stale_years: int,
) -> gpd.GeoDataFrame:
    """One row per grid cell that holds a palm, sorted by ``cell_id`` (EPSG:4326).

    ``inventory_vintage`` and ``lidar_vintage`` are the median vintage years (NaN when none).
    ``stale`` is ``run_year - min(vintages) > stale_years``; a cell with no vintage is not stale.
    """
    if step_deg <= 0:
        raise ValueError("step_deg must be positive")
    counts: dict[tuple[int, int], int] = defaultdict(int)
    inv: dict[tuple[int, int], list[int]] = defaultdict(list)
    lid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for palm in palms:
        cell = (_cell_index(palm.lon, step_deg), _cell_index(palm.lat, step_deg))
        counts[cell] += 1
        inventory, lidar = _palm_years(palm)
        inv[cell].extend(inventory)
        lid[cell].extend(lidar)

    rows: list[dict[str, Any]] = []
    for cell, count in counts.items():
        ix, iy = cell
        inventory_v = _median(inv[cell])
        lidar_v = _median(lid[cell])
        known = [v for v in (inventory_v, lidar_v) if v is not None]
        rows.append(
            {
                "cell_id": _cell_label(ix, iy, step_deg),
                "palm_count": count,
                "inventory_vintage": inventory_v if inventory_v is not None else math.nan,
                "lidar_vintage": lidar_v if lidar_v is not None else math.nan,
                "stale": bool(known) and (run_year - min(known)) > stale_years,
                "geometry": box(
                    ix * step_deg, iy * step_deg, (ix + 1) * step_deg, (iy + 1) * step_deg
                ),
            }
        )
    rows.sort(key=lambda r: str(r["cell_id"]))
    frame = pd.DataFrame(rows, columns=list(_GRID_COLUMNS)).astype(
        {
            "cell_id": "object",
            "palm_count": "int64",
            "inventory_vintage": "float64",
            "lidar_vintage": "float64",
            "stale": "bool",
        }
    )
    return gpd.GeoDataFrame(frame, geometry="geometry", crs=_WGS84)


# ---------------------------------------------------------------------------------------------
# Layer frames


def _frame(columns: Columns, geometry: list[BaseGeometry]) -> gpd.GeoDataFrame:
    """GeoDataFrame with explicit dtypes, so an empty layer keeps its schema."""
    data = {name: pd.Series(values, dtype=dtype) for name, (dtype, values) in columns.items()}
    return gpd.GeoDataFrame(data, geometry=gpd.GeoSeries(geometry, crs=_WGS84), crs=_WGS84)


def _json(value: dict[str, str]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _buffers(
    rows: list[tuple[str, PalmRecord]],
    crs: pyproj.CRS | None,
    radii: list[float],
    extra: Columns,
) -> gpd.GeoDataFrame:
    """Circles around each palm, buffered in the local CRS and returned in EPSG:4326."""
    geoms: list[BaseGeometry] = []
    if rows:
        if crs is None:
            raise ValueError("a local CRS is required to buffer palms")
        centres = gpd.GeoSeries([Point(p.lon, p.lat) for _, p in rows], crs=_WGS84).to_crs(crs)
        circles = [
            centre.buffer(radius, quad_segs=_QUAD_SEGS)
            for centre, radius in zip(centres, radii, strict=True)
        ]
        geoms = list(gpd.GeoSeries(circles, crs=crs).to_crs(_WGS84))
    columns: Columns = {"palm_id": ("object", [pid for pid, _ in rows])}
    columns.update(extra)
    return _frame(columns, geoms)


def _palm_frames(
    palms: Sequence[PalmRecord], id_prefix: str, crs: pyproj.CRS | None
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, gpd.GeoDataFrame]:
    palm_ids = assign_palm_ids(palms, id_prefix)
    order = sorted(range(len(palms)), key=lambda i: palm_ids[i])
    rows = [(palm_ids[i], palms[i]) for i in order]
    recs = [p for _, p in rows]

    palm_cols: Columns = {
        "palm_id": ("object", [pid for pid, _ in rows]),
        "stable_key": ("object", [stable_key_for(p) for p in recs]),
        "species": ("object", [p.species for p in recs]),
        "species_confidence": ("float64", [p.species_confidence for p in recs]),
        "species_source": ("object", [p.species_source for p in recs]),
        "height_m": ("float64", [p.height_m for p in recs]),
        "height_source": ("object", [p.height_source for p in recs]),
        "crown_diam_m": ("float64", [p.crown_diam_m for p in recs]),
        "ground_elev_m": ("float64", [p.ground_elev_m for p in recs]),
        "detected_by": ("object", [p.detected_by for p in recs]),
        "source_ids": ("object", [";".join(sorted(p.source_ids)) for p in recs]),
        "exclusion_radius_m": ("float64", [p.exclusion_radius_m for p in recs]),
        "building_conflict": ("bool", [p.building_conflict for p in recs]),
        "data_vintage": ("object", [_json(p.data_vintage) for p in recs]),
        "species_raw": ("object", [p.species_raw for p in recs]),
    }
    palms_gdf = _frame(palm_cols, [Point(p.lon, p.lat) for p in recs])

    sized = [(pid, p) for pid, p in rows if p.exclusion_radius_m is not None]
    exclusion = _buffers(
        sized,
        crs,
        [float(p.exclusion_radius_m or 0.0) for _, p in sized],
        {
            "exclusion_radius_m": ("float64", [p.exclusion_radius_m for _, p in sized]),
            "building_conflict": ("bool", [p.building_conflict for _, p in sized]),
        },
    )
    check = _buffers(rows, crs, [CHECK_RADIUS_M] * len(rows), {})
    return palms_gdf, exclusion, check


def _rejects_frame(rejects: Sequence[Reject]) -> gpd.GeoDataFrame:
    ordered = sorted_rejects(rejects)
    columns: Columns = {
        "stage": ("object", [r.stage for r in ordered]),
        "source": ("object", [r.source for r in ordered]),
        "source_id": ("object", [r.source_id for r in ordered]),
        "lon": ("float64", [r.lon for r in ordered]),
        "lat": ("float64", [r.lat for r in ordered]),
        "reason": ("object", [r.reason for r in ordered]),
        "all_reasons": ("object", [";".join(r.all_reasons) for r in ordered]),
        "species_raw": ("object", [r.species_raw for r in ordered]),
    }
    for name in METRIC_COLUMNS:
        columns[name] = ("float64", [r.metrics.get(name) for r in ordered])
    return _frame(columns, [Point(r.lon, r.lat) for r in ordered])


def _buildings_frame(buildings: Sequence[ConflictBuilding]) -> gpd.GeoDataFrame:
    ordered = sorted(buildings, key=lambda b: (b.source, b.building_id))
    return _frame(
        {
            "building_id": ("object", [b.building_id for b in ordered]),
            "source": ("object", [b.source for b in ordered]),
        },
        [b.geometry for b in ordered],
    )


def _candidates_frame(candidates: Sequence[LidarCandidate]) -> gpd.GeoDataFrame:
    ordered = sorted(candidates, key=lambda c: c.candidate_id)
    floats = (
        "x",
        "y",
        "lon",
        "lat",
        "height_m",
        "crown_area_m2",
        "crown_diam_m",
        "ratio",
        "shared_boundary_frac",
        "ground_elev_m",
    )
    columns: Columns = {
        "candidate_id": ("object", [c.candidate_id for c in ordered]),
        "dataset": ("object", [c.dataset for c in ordered]),
    }
    for name in floats:
        columns[name] = ("float64", [getattr(c, name) for c in ordered])
    columns["in_building"] = ("bool", [c.in_building for c in ordered])
    columns["accepted"] = ("bool", [c.accepted for c in ordered])
    columns["reasons"] = ("object", [";".join(c.reasons) for c in ordered])
    columns["vintage"] = ("object", [c.vintage for c in ordered])
    return _frame(columns, [Point(c.lon, c.lat) for c in ordered])


def _crowns_frame(crowns: Sequence[tuple[str, BaseGeometry]]) -> gpd.GeoDataFrame:
    ordered = sorted(crowns, key=lambda c: c[0])
    return _frame({"candidate_id": ("object", [c[0] for c in ordered])}, [c[1] for c in ordered])


# ---------------------------------------------------------------------------------------------
# Writer

_GEOMETRY_TYPES: Final = {
    "palms": "Point",
    "exclusion_circles": "Polygon",
    "check_radius_3m": "Polygon",
    "rejects": "Point",
    "building_conflicts": "Polygon",
    "vintage_grid": "Polygon",
    CANDIDATES_LAYER: "Point",
    CROWNS_LAYER: "Polygon",
}


def _remove_existing(path: Path) -> None:
    for suffix in ("", "-wal", "-shm", "-journal"):
        sibling = path.with_name(path.name + suffix)
        if sibling.exists():
            sibling.unlink()


def write_qa_gpkg(
    path: Path,
    palms: Sequence[PalmRecord],
    rejects: Sequence[Reject],
    conflict_buildings: Sequence[ConflictBuilding],
    vintage_grid: gpd.GeoDataFrame,
    candidates: Sequence[LidarCandidate] | None = None,
    crowns: Sequence[tuple[str, BaseGeometry]] | None = None,
    *,
    id_prefix: str = DEFAULT_ID_PREFIX,
    crs: pyproj.CRS | str | None = None,
) -> None:
    """Write all QA layers to ``path`` (an existing file is deleted first).

    ``id_prefix`` is the region's palm id prefix, so ``palm_id`` matches ``palms.geojson``.
    ``crs`` is the local metric CRS for the buffers; by default the UTM zone of the palms.
    ``candidates`` and ``crowns`` (Phase 4) add their layers only when given.
    """
    local: pyproj.CRS | None
    if crs is not None:
        local = pyproj.CRS.from_user_input(crs)
    elif palms:
        lons = [p.lon for p in palms]
        lats = [p.lat for p in palms]
        local = geo.local_crs([min(lons), min(lats), max(lons), max(lats)])
    else:
        local = None

    palms_gdf, exclusion, check = _palm_frames(palms, id_prefix, local)
    layers: list[tuple[str, gpd.GeoDataFrame]] = [
        ("palms", palms_gdf),
        ("exclusion_circles", exclusion),
        ("check_radius_3m", check),
        ("rejects", _rejects_frame(rejects)),
        ("building_conflicts", _buildings_frame(conflict_buildings)),
        ("vintage_grid", vintage_grid),
    ]
    if candidates is not None:
        layers.append((CANDIDATES_LAYER, _candidates_frame(candidates)))
    if crowns is not None:
        layers.append((CROWNS_LAYER, _crowns_frame(crowns)))

    path.parent.mkdir(parents=True, exist_ok=True)
    _remove_existing(path)
    for name, frame in layers:
        frame.to_file(
            path,
            driver="GPKG",
            layer=name,
            engine="pyogrio",
            geometry_type=_GEOMETRY_TYPES[name],
        )
