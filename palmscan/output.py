"""Turn ``PalmRecord`` objects into a schema-valid ``palms.geojson``.

This module only maps palmscan's model onto the contract. Palm ids come from
``palmcore.ids``, the canonical text form (rounding, key order, sorting, layout, atomic write)
belongs to ``palmcore.palms`` and validation to ``palmcore.contract``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from palmcore import contract, ids
from palmcore.errors import ContractError
from palmcore.palms import PalmsMeta, dump_palms, write_palms_doc
from palmscan.model import PalmRecord

__all__ = [
    "INVALID_FILENAME",
    "assign_palm_ids",
    "stable_key_for",
    "to_feature_collection",
    "validate_palms",
    "write_invalid",
    "write_palms",
]

INVALID_FILENAME = "palms.invalid.geojson"
_LIDAR_PREFIX = "lidar:"
_MAX_NAMED = 5


def _describe(palm: PalmRecord) -> str:
    return f"{palm.stable_key!r} (source_ids={sorted(palm.source_ids)})"


def stable_key_for(palm: PalmRecord) -> str:
    """The key a palm's id is derived from.

    Inventory and OSM palms use their smallest source id (``palmcore.ids.palm_key``); source ids
    of the form ``lidar:...`` are not stable across runs and are ignored. LiDAR-only palms use
    ``lidar:<dataset>:<round(x)>:<round(y)>`` (local metres). A palm with neither falls back to
    its location on a 1 m grid.
    """
    stable = [s for s in palm.source_ids if not s.startswith(_LIDAR_PREFIX)]
    if palm.lidar is not None:
        fallback = f"lidar:{palm.lidar.dataset}:{round(palm.x)}:{round(palm.y)}"
    else:
        fallback = ids.location_key(palm.lon, palm.lat)
    return ids.palm_key(stable, fallback)


def assign_palm_ids(palms: Sequence[PalmRecord], prefix: str) -> list[str]:
    """Return one palm id per record, in input order.

    Raises ``ContractError`` naming the records involved when two records share an id.
    """
    keys = [stable_key_for(p) for p in palms]
    palm_ids = [ids.palm_id(prefix, key) for key in keys]
    try:
        ids.assert_unique(palm_ids, "palm_id")
    except ContractError as exc:
        by_id: dict[str, list[PalmRecord]] = {}
        for palm_id, palm in zip(palm_ids, palms, strict=True):
            by_id.setdefault(palm_id, []).append(palm)
        lines = []
        for palm_id in exc.issues:
            named = ", ".join(_describe(p) for p in by_id[palm_id][:_MAX_NAMED])
            lines.append(f"{palm_id}: {named}")
        raise ContractError(
            "duplicate palm_id from records: " + "; ".join(lines), exc.issues
        ) from exc
    return palm_ids


def _feature(palm: PalmRecord, palm_id: str, region: str) -> dict[str, Any]:
    props: dict[str, Any] = {
        "palm_id": palm_id,
        "species": palm.species,
        "species_confidence": palm.species_confidence,
        "species_source": palm.species_source,
        "height_m": palm.height_m,
        "height_source": palm.height_source,
        "crown_diam_m": palm.crown_diam_m,
        "ground_elev_m": palm.ground_elev_m,
        "detected_by": palm.detected_by,
        "source_ids": sorted(palm.source_ids),
        "exclusion_radius_m": palm.exclusion_radius_m,
        "building_conflict": palm.building_conflict,
        "data_vintage": dict(palm.data_vintage),
        "region": region,
    }
    return {
        "type": "Feature",
        "id": palm_id,
        "geometry": {"type": "Point", "coordinates": [palm.lon, palm.lat]},
        "properties": props,
    }


def to_feature_collection(
    palms: Sequence[PalmRecord],
    region: str,
    *,
    id_prefix: str,
    meta: PalmsMeta,
) -> dict[str, Any]:
    """Build the canonical FeatureCollection (rounded, contract key order, sorted by palm_id).

    Missing values stay ``None`` so that ``validate_palms`` reports them instead of this
    function guessing. ``meta`` carries the file-level fields, so a fixed ``generated_at``
    gives identical output for identical input.
    """
    if meta.region != region:
        raise ValueError(f"meta.region {meta.region!r} does not match region {region!r}")
    palm_ids = assign_palm_ids(palms, id_prefix)
    doc: dict[str, Any] = {
        "type": "FeatureCollection",
        "schema_version": meta.schema_version,
        "region": region,
        "generated_at": meta.generated_at,
        "data_version": meta.data_version,
        "generator": {"name": meta.generator_name, "version": meta.generator_version},
        "config_sha256": meta.config_sha256,
        "features": [_feature(p, i, region) for p, i in zip(palms, palm_ids, strict=True)],
    }
    canonical: dict[str, Any] = json.loads(dump_palms(doc))
    return canonical


def validate_palms(fc: Mapping[str, Any]) -> list[str]:
    """Contract errors for ``fc`` as readable strings (empty when valid; warnings excluded)."""
    try:
        report = contract.validate_palms(fc, mode="write")
    except ContractError as exc:
        return [str(exc)]
    return [str(issue) for issue in report.errors]


def write_palms(fc: Mapping[str, Any], path: Path) -> None:
    """Validate and write ``fc`` atomically; invalid input raises ``ContractError``, no file."""
    write_palms_doc(path, fc)


def write_invalid(fc: Mapping[str, Any], directory: Path) -> Path:
    """Dump ``fc`` as plain JSON to ``<directory>/palms.invalid.geojson`` for inspection."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / INVALID_FILENAME
    path.write_text(
        json.dumps(fc, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return path
