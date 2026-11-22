"""``mask_out`` areas: load them from the region config and drop palms inside them (plan W7).

Masks are polygons in lon/lat. A palm on a mask edge counts as inside, and a palm inside two
masks is reported under the first one, as in ``palmgen``. Every ``kind`` (``mod``, ``airport``,
``other``) removes palms here. The default airport masks (``masks.airports``) are applied by
``palmgen``, not by palmscan.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import shapely
from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from palmcore.config import MaskArea
from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmscan.model import PalmRecord, Reject

__all__ = ["apply_masks", "load_masks"]

log = get_logger(__name__)


def _geometries_in(doc: Any) -> list[Mapping[str, Any]]:
    """GeoJSON geometry objects in a FeatureCollection, Feature, GeometryCollection or geometry."""
    if not isinstance(doc, Mapping):
        return []
    kind = doc.get("type")
    if kind == "FeatureCollection":
        feats = doc.get("features")
        out: list[Mapping[str, Any]] = []
        for feature in feats if isinstance(feats, list) else []:
            out.extend(_geometries_in(feature))
        return out
    if kind == "Feature":
        geom = doc.get("geometry")
        return [geom] if isinstance(geom, Mapping) else []
    if kind == "GeometryCollection":
        geoms = doc.get("geometries")
        return [g for g in geoms if isinstance(g, Mapping)] if isinstance(geoms, list) else []
    return [doc] if "coordinates" in doc else []


def _polygons(geom: BaseGeometry) -> list[BaseGeometry]:
    """Non-empty polygons in ``geom`` (repaired if invalid); lines and points are dropped."""
    out: list[BaseGeometry] = []
    for part in shapely.get_parts(shapely.make_valid(geom) if not geom.is_valid else geom):
        if part.geom_type == "Polygon":
            if not part.is_empty:
                out.append(part)
        elif part.geom_type == "GeometryCollection":
            out.extend(_polygons(part))
    return out


def _shape(geometry: Mapping[str, Any], where: str) -> list[BaseGeometry]:
    try:
        return _polygons(shape(geometry))
    except (ValueError, TypeError, KeyError, shapely.errors.ShapelyError) as exc:
        raise ConfigError(f"{where}: bad geometry: {exc}") from exc


def _area_geometry(area: MaskArea, base_dir: Path) -> BaseGeometry:
    where = f"mask_out {area.name!r}"
    pieces: list[BaseGeometry] = []
    if area.bbox is not None:
        pieces.append(box(*area.bbox.as_tuple()))
    if area.geometry is not None:
        pieces.extend(_shape(area.geometry, f"{where} geometry"))
    if area.path is not None:
        path = area.path if area.path.is_absolute() else base_dir / area.path
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise ConfigError(f"{where}: cannot read {path}: {exc}") from exc
        except ValueError as exc:
            raise ConfigError(f"{where}: {path} is not valid JSON: {exc}") from exc
        for index, geometry in enumerate(_geometries_in(doc)):
            pieces.extend(_shape(geometry, f"{where} file {path.name} geometry {index}"))
    if not pieces:
        raise ConfigError(f"{where} has no polygon area (bbox, geometry or path)")
    return unary_union(pieces)


def load_masks(mask_out: Sequence[MaskArea], base_dir: Path) -> list[tuple[str, BaseGeometry]]:
    """``(name, polygon in lon/lat)`` for each ``mask_out`` item, in config order.

    Paths in :class:`~palmcore.config.MaskArea` are already absolute; ``base_dir`` only resolves
    a relative one. An item with no polygon area, or an unreadable file, raises ``ConfigError``.
    """
    return [(area.name, _area_geometry(area, base_dir)) for area in mask_out]


def apply_masks(
    palms: Sequence[PalmRecord], masks: Sequence[tuple[str, BaseGeometry]]
) -> tuple[list[PalmRecord], list[Reject]]:
    """Palms outside every mask, and a ``Reject(stage="mask", reason="mask_out:<name>")`` per
    palm inside one. Kept palms and rejects keep their input order."""
    if not masks or not palms:
        return list(palms), []
    lons = np.array([p.lon for p in palms], dtype=float)
    lats = np.array([p.lat for p in palms], dtype=float)
    owner: list[str | None] = [None] * len(palms)
    free = np.ones(len(palms), dtype=bool)
    for name, geometry in masks:
        inside = np.zeros(len(palms), dtype=bool)
        inside[free] = shapely.intersects_xy(geometry, lons[free], lats[free])
        for index in np.flatnonzero(inside):
            owner[int(index)] = name
        free &= ~inside
    kept: list[PalmRecord] = []
    rejects: list[Reject] = []
    for palm, owner_name in zip(palms, owner, strict=True):
        if owner_name is None:
            kept.append(palm)
            continue
        source, _, source_id = palm.stable_key.partition(":")
        reason = f"mask_out:{owner_name}"
        rejects.append(
            Reject(
                stage="mask",
                source=source,
                source_id=source_id or palm.stable_key,
                lon=palm.lon,
                lat=palm.lat,
                reason=reason,
                all_reasons=[reason],
                species_raw=palm.species_raw,
            )
        )
    if rejects:
        log.info("mask_out removed %d of %d palms", len(rejects), len(palms))
    return kept, rejects
