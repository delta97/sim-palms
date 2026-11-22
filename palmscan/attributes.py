"""Palm attributes (plan W7): height, crown, exclusion radius and building conflicts.

Sizes come from, in order: a plausible inventory height, a region median (Phase 4), the
species row, the genus row, then the ``_default`` row of ``data/species_defaults.yaml``.
Palms measured by LiDAR keep their LiDAR values. The exclusion radius uses the region's
``exclusion:`` clamps (``palmcore.config.ExclusionConfig``), the same rule as ``palmgen``.
"""

from __future__ import annotations

import functools
import math
import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final

import yaml

from palmcore.config import ExclusionConfig
from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmscan import geo
from palmscan.config import ScanConfig
from palmscan.model import PalmRecord
from palmscan.species_names import read_data_text

if TYPE_CHECKING:
    from geopandas import GeoDataFrame

__all__ = [
    "assign_exclusion",
    "assign_sizes",
    "default_size",
    "flag_building_conflicts",
    "parse_height",
]

log = get_logger(__name__)

FEET_TO_M: Final = 0.3048
_DEFAULT_UNITS: Final = "ft"
_SIZE_DECIMALS: Final = 1  # the precision palms.geojson stores height_m and crown_diam_m at
_RADIUS_DECIMALS: Final = 2
_NUMBER: Final = r"(\d+(?:\.\d+)?|\.\d+)"
_DASHES: Final = chr(0x2013) + "|" + chr(0x2014)  # en dash, em dash
_UNIT: Final = r"(ft|feet|foot|m|meters|metres|meter|metre|')"
_HEIGHT_RE: Final = re.compile(
    rf"^{_NUMBER}\s*{_UNIT}?(?:\s*(?:-|{_DASHES}|to)\s*{_NUMBER})?\s*{_UNIT}?$"
)
_FOOT_UNITS: Final = frozenset({"ft", "feet", "foot", "'"})


def parse_height(raw: str | None, units: str = "ft") -> float | None:
    """Height in metres from inventory text, or ``None`` when it is not a number or range.

    Accepts ``"35"``, ``"35.5"``, ranges (``"30-45"``, ``"30 to 45"``: midpoint) and a unit
    suffix (``ft``, ``'``, ``m``) that overrides ``units``. Class labels such as ``"Large"``,
    zero and negative values give ``None``. The result is not rounded.
    """
    if units not in ("ft", "m"):
        raise ValueError(f"units must be 'ft' or 'm', got {units!r}")
    if raw is None:
        return None
    match = _HEIGHT_RE.match(raw.strip().lower())
    if match is None:
        return None
    low, unit_a, high, unit_b = match.groups()
    if (
        unit_a is not None
        and unit_b is not None
        and (unit_a in _FOOT_UNITS) != (unit_b in _FOOT_UNITS)
    ):
        return None
    unit = unit_b or unit_a
    value = float(low) if high is None else (float(low) + float(high)) / 2.0
    if not math.isfinite(value) or value <= 0:
        return None
    in_feet = (unit in _FOOT_UNITS) if unit is not None else units == "ft"
    return value * FEET_TO_M if in_feet else value


@functools.cache
def _size_tables() -> tuple[
    Mapping[str, tuple[float, float]], Mapping[str, tuple[float, float]], tuple[float, float]
]:
    """(species rows, genus rows, default row), each ``(height_m, crown_diam_m)``."""
    try:
        data = yaml.safe_load(read_data_text("species_defaults.yaml"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot load species_defaults.yaml: {exc}") from exc
    if not isinstance(data, dict) or "_default" not in data or "_genus" not in data:
        raise ConfigError("species_defaults.yaml: needs '_genus' and '_default'")

    def row(name: str, value: Any) -> tuple[float, float]:
        try:
            return float(value["height_m"]), float(value["crown_diam_m"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ConfigError(f"species_defaults.yaml: bad row {name!r}") from exc

    species = {k: row(k, v) for k, v in data.items() if k not in ("_genus", "_default")}
    genus = {k: row(k, v) for k, v in data["_genus"].items()}
    return species, genus, row("_default", data["_default"])


def default_size(species: str | None) -> tuple[float, float]:
    """``(height_m, crown_diam_m)`` for a species key: species row, genus row, then default."""
    by_species, by_genus, fallback = _size_tables()
    if species is None:
        return fallback
    if species in by_species:
        return by_species[species]
    return by_genus.get(species.split("_", 1)[0], fallback)


def _height_units(cfg: ScanConfig, palm: PalmRecord) -> str:
    for source in cfg.region.sources.inventory:
        if palm.stable_key.startswith(source.name + ":"):
            return source.height_units
    return _DEFAULT_UNITS


def _inventory_height(cfg: ScanConfig, palm: PalmRecord) -> float | None:
    """Plausible inventory height in metres: an ingested value or the parsed ``height_raw``."""
    if palm.height_source == "inventory" and palm.height_m is not None:
        height: float | None = palm.height_m
    else:
        height = parse_height(palm.height_raw, _height_units(cfg, palm))
    if height is None or not cfg.inventory.height_min_m <= height <= cfg.inventory.height_max_m:
        return None
    return height


def assign_sizes(
    palms: Sequence[PalmRecord],
    cfg: ScanConfig,
    region_medians: Mapping[str, float] | None = None,
) -> None:
    """Set ``height_m``, ``height_source`` and, when missing, ``crown_diam_m`` in place.

    Palms with ``height_source == "lidar"`` are left alone. Inventory heights outside
    ``cfg.inventory.height_min_m..height_max_m`` are ignored. Values are rounded to 0.1 m, the
    precision stored in ``palms.geojson``, so :func:`assign_exclusion` matches what is written.
    """
    medians = region_medians or {}
    for palm in palms:
        if palm.height_source == "lidar":
            continue
        default_height, default_crown = default_size(palm.species)
        height = _inventory_height(cfg, palm)
        if height is not None:
            source = "inventory"
        elif palm.species is not None and palm.species in medians:
            height, source = float(medians[palm.species]), "region_median"
        else:
            height, source = default_height, "species_default"
        palm.height_m = round(height, _SIZE_DECIMALS)
        palm.height_source = source
        if palm.crown_diam_m is None:
            palm.crown_diam_m = round(default_crown, _SIZE_DECIMALS)


def assign_exclusion(palms: Sequence[PalmRecord], exclusion: ExclusionConfig) -> None:
    """Set ``exclusion_radius_m`` = ``crown_diam_m / 2 + margin_m`` clamped to the region range.

    The crown is taken at 0.1 m, as written to ``palms.geojson``, and the radius is rounded to
    0.01. A palm with no crown gets ``default_radius_m`` (clamped).
    """
    for palm in palms:
        if palm.crown_diam_m is None:
            radius = exclusion.default_radius_m
        else:
            radius = round(palm.crown_diam_m, _SIZE_DECIMALS) / 2.0 + exclusion.margin_m
        radius = min(max(radius, exclusion.radius_min_m), exclusion.radius_max_m)
        palm.exclusion_radius_m = round(radius, _RADIUS_DECIMALS)


def flag_building_conflicts(
    palms: Sequence[PalmRecord],
    buildings: GeoDataFrame,
    crs: str,
    overlap_min_m2: float = 0.1,
) -> GeoDataFrame:
    """Set ``building_conflict`` on each palm and return the conflicting buildings.

    A palm conflicts when its exclusion circle (32-segment, in the metric ``crs``) overlaps a
    building by more than ``overlap_min_m2``. Needs ``exclusion_radius_m`` (see
    :func:`assign_exclusion`). The result is in EPSG:4326, one row per building, sorted by
    ``building_id``. A frame with no CRS is taken to be EPSG:4326.
    """
    import numpy as np
    import shapely
    from shapely import STRtree

    missing = [p.stable_key for p in palms if p.exclusion_radius_m is None]
    if missing:
        raise ValueError(f"exclusion_radius_m not set (call assign_exclusion): {missing[:3]}")
    for palm in palms:
        palm.building_conflict = False

    frame = buildings if buildings.crs is not None else buildings.set_crs(geo.WGS84)
    if len(palms) == 0 or len(frame) == 0:
        return frame.iloc[0:0].to_crs(geo.WGS84)

    local = frame.to_crs(crs)
    geoms = np.array(
        [g if g.is_valid else shapely.make_valid(g) for g in local.geometry], dtype=object
    )
    xs, ys = geo.to_local([p.lon for p in palms], [p.lat for p in palms], crs)
    centres = shapely.points(np.asarray(xs), np.asarray(ys))
    radii = np.array([p.exclusion_radius_m for p in palms], dtype=float)
    circles = shapely.buffer(centres, radii, quad_segs=8)

    palm_idx, bldg_idx = STRtree(geoms).query(circles, predicate="intersects")
    overlap = shapely.area(shapely.intersection(circles[palm_idx], geoms[bldg_idx]))
    hit = overlap > overlap_min_m2
    for i in np.unique(palm_idx[hit]):
        palms[int(i)].building_conflict = True

    out = frame.iloc[np.unique(bldg_idx[hit])]
    if "building_id" in out.columns:
        out = out.drop_duplicates(subset="building_id").sort_values("building_id")
    return out.reset_index(drop=True).to_crs(geo.WGS84)
