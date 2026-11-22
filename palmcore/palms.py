"""Read and write palms.geojson: one canonical serializer so the same input gives the same bytes.

Validation always goes through `palmcore.contract`; this module only defines the typed record,
the canonical text form (rounding, key order, sorting, layout) and the file I/O.
"""

from __future__ import annotations

import contextlib
import copy
import json
import math
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from palmcore.cache import atomic_write_text
from palmcore.contract import (
    PALMS_SCHEMA_VERSION,
    ValidationReport,
    check_version,
    validate_palms,
)
from palmcore.errors import ConfigError, ContractError
from palmcore.log import get_logger

log = get_logger("palmcore.palms")

_FILE_KEYS: Final = (
    "type",
    "schema_version",
    "region",
    "generated_at",
    "data_version",
    "generator",
    "config_sha256",
    "bbox",
)
_PROPERTY_KEYS: Final = (
    "palm_id",
    "species",
    "species_confidence",
    "species_source",
    "height_m",
    "height_source",
    "crown_diam_m",
    "ground_elev_m",
    "detected_by",
    "source_ids",
    "exclusion_radius_m",
    "building_conflict",
    "data_vintage",
    "region",
)
_DECIMALS: Final = {
    "height_m": 1,
    "crown_diam_m": 1,
    "ground_elev_m": 1,
    "exclusion_radius_m": 2,
    "species_confidence": 2,
}
_COORD_DECIMALS: Final = 7
_TIME_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True, slots=True)
class Palm:
    palm_id: str
    lon: float
    lat: float
    species: str
    species_confidence: float
    species_source: str
    height_m: float
    height_source: str
    crown_diam_m: float
    ground_elev_m: float | None
    detected_by: str
    source_ids: tuple[str, ...]
    exclusion_radius_m: float
    building_conflict: bool
    data_vintage: Mapping[str, str]
    region: str
    extra: Mapping[str, Any] = field(default_factory=dict)  # x_* and unknown newer-minor fields

    def to_feature(self) -> dict[str, Any]:
        """The GeoJSON feature, not yet rounded or ordered (`dump_palms` does that)."""
        props: dict[str, Any] = {
            "palm_id": self.palm_id,
            "species": self.species,
            "species_confidence": self.species_confidence,
            "species_source": self.species_source,
            "height_m": self.height_m,
            "height_source": self.height_source,
            "crown_diam_m": self.crown_diam_m,
            "ground_elev_m": self.ground_elev_m,
            "detected_by": self.detected_by,
            "source_ids": list(self.source_ids),
            "exclusion_radius_m": self.exclusion_radius_m,
            "building_conflict": self.building_conflict,
            "data_vintage": dict(self.data_vintage),
            "region": self.region,
        }
        for key, value in self.extra.items():
            props.setdefault(key, copy.deepcopy(value))
        return {
            "type": "Feature",
            "id": self.palm_id,
            "geometry": {"type": "Point", "coordinates": [self.lon, self.lat]},
            "properties": props,
        }

    @classmethod
    def from_feature(cls, feature: Mapping[str, Any]) -> Palm:
        """Build a Palm from a schema-valid feature; non-standard properties go to `extra`."""
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        return cls(
            palm_id=props["palm_id"],
            lon=lon,
            lat=lat,
            species=props["species"],
            species_confidence=props["species_confidence"],
            species_source=props["species_source"],
            height_m=props["height_m"],
            height_source=props["height_source"],
            crown_diam_m=props["crown_diam_m"],
            ground_elev_m=props["ground_elev_m"],
            detected_by=props["detected_by"],
            source_ids=tuple(props["source_ids"]),
            exclusion_radius_m=props["exclusion_radius_m"],
            building_conflict=props["building_conflict"],
            data_vintage=dict(props["data_vintage"]),
            region=props["region"],
            extra={k: v for k, v in props.items() if k not in _PROPERTY_KEYS},
        )


@dataclass(frozen=True)
class PalmsMeta:
    schema_version: str
    region: str
    generated_at: str
    data_version: str
    generator_name: str
    generator_version: str
    config_sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        """Collection metadata as a plain dict; `data_version` is what palmgen reads."""
        return {
            "schema_version": self.schema_version,
            "region": self.region,
            "generated_at": self.generated_at,
            "data_version": self.data_version,
            "generator_name": self.generator_name,
            "generator_version": self.generator_version,
            "config_sha256": self.config_sha256,
        }


@dataclass
class PalmCollection:
    meta: PalmsMeta
    palms: list[Palm]  # sorted by palm_id
    report: ValidationReport

    def by_id(self) -> dict[str, Palm]:
        return {p.palm_id: p for p in self.palms}


# --- canonical form ----------------------------------------------------------------------------


def _round(value: Any, decimals: int) -> Any:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return value
    rounded = round(float(value), decimals)
    return 0.0 if rounded == 0 else rounded  # also turns -0.0 into 0.0


def _check_finite(value: Any, path: str) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError(f"non-finite number {value} at {path or 'file'}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _check_finite(item, f"{path}.{key}")
    elif isinstance(value, list | tuple):
        for i, item in enumerate(value):
            _check_finite(item, f"{path}[{i}]")


def _plain(value: Any) -> Any:
    """Deep copy into plain dicts/lists, mappings with sorted keys, -0.0 normalised."""
    if isinstance(value, Mapping):
        return {str(k): _plain(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if isinstance(value, float) and value == 0:
        return 0.0
    return copy.deepcopy(value)


def _ordered(mapping: Mapping[str, Any], first: tuple[str, ...]) -> dict[str, Any]:
    out = {k: mapping[k] for k in first if k in mapping}
    out.update({k: mapping[k] for k in sorted(mapping) if k not in out})
    return out


def _canonical_feature(feature: Any) -> Any:
    if not isinstance(feature, Mapping):
        return _plain(feature)
    out = _plain(feature)
    geometry = out.get("geometry")
    if isinstance(geometry, dict) and isinstance(geometry.get("coordinates"), list):
        geometry["coordinates"] = [_round(c, _COORD_DECIMALS) for c in geometry["coordinates"]]
        out["geometry"] = _ordered(geometry, ("type", "coordinates"))
    props = feature.get("properties")
    new_props: Any = None
    if isinstance(props, Mapping):
        new_props = _plain(props)
        for key, decimals in _DECIMALS.items():
            if key in new_props:
                new_props[key] = _round(new_props[key], decimals)
        if isinstance(new_props.get("source_ids"), list):
            with contextlib.suppress(TypeError):  # mixed types: leave for the validator
                new_props["source_ids"] = sorted(new_props["source_ids"])
        vintage = new_props.get("data_vintage")
        if isinstance(vintage, dict):
            new_props["data_vintage"] = {k: vintage[k] for k in sorted(vintage)}
        new_props = _ordered(new_props, _PROPERTY_KEYS)
        out["id"] = new_props.get("palm_id", out.get("id"))
        if out["id"] is None:
            del out["id"]
        out["properties"] = new_props
    return _ordered(out, ("type", "id", "geometry", "properties"))


def _sort_key(feature: Any) -> str:
    if isinstance(feature, Mapping):
        props = feature.get("properties")
        if isinstance(props, Mapping) and isinstance(props.get("palm_id"), str):
            return str(props["palm_id"])
    return ""


def _canonical_doc(doc: Mapping[str, Any]) -> dict[str, Any]:
    _check_finite(doc, "")
    features = doc.get("features")
    head = {k: v for k, v in doc.items() if k != "features"}
    out = _ordered(_plain(head), _FILE_KEYS)
    if isinstance(out.get("bbox"), list):
        out["bbox"] = [_round(c, _COORD_DECIMALS) for c in out["bbox"]]
    if isinstance(features, list | tuple):
        canon = [_canonical_feature(f) for f in features]
        out["features"] = sorted(canon, key=_sort_key)
    elif "features" in doc:
        out["features"] = _plain(features)
    return out


def _text(canonical: Mapping[str, Any]) -> str:
    return json.dumps(canonical, indent=1, ensure_ascii=False, allow_nan=False) + "\n"


def dump_palms(doc: Mapping[str, Any]) -> str:
    """Canonical text for a FeatureCollection: rounding, key order, sorting, layout."""
    return _text(_canonical_doc(doc))


# --- writing -----------------------------------------------------------------------------------


def write_palms_doc(path: Path, doc: Mapping[str, Any]) -> None:
    """Canonicalise, validate in write mode, then write atomically. Invalid: nothing is written."""
    canonical = _canonical_doc(doc)
    validate_palms(canonical, mode="write").raise_for_errors()
    atomic_write_text(path, _text(canonical))


def _resolve_generated_at(value: datetime | None) -> datetime:
    if value is not None:
        moment = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return moment.astimezone(UTC).replace(microsecond=0)
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        try:
            return datetime.fromtimestamp(int(epoch), UTC)
        except (ValueError, OverflowError, OSError) as exc:
            raise ConfigError(f"SOURCE_DATE_EPOCH must be integer seconds, got {epoch!r}") from exc
    return datetime.now(UTC).replace(microsecond=0)


def write_palms(
    path: Path,
    palms: Iterable[Palm],
    *,
    region: str,
    generator_name: str,
    generator_version: str,
    config_sha256: str | None = None,
    generated_at: datetime | None = None,
    data_version: str | None = None,
) -> PalmsMeta:
    """Build a palms.geojson document from `palms`, validate and write it, return its metadata.

    `generated_at` falls back to SOURCE_DATE_EPOCH, then now; a naive datetime is taken as UTC.
    `data_version` falls back to the YYYY-MM of `generated_at`.
    """
    moment = _resolve_generated_at(generated_at)
    stamp = moment.strftime(_TIME_FORMAT)
    version = data_version if data_version is not None else moment.strftime("%Y-%m")
    doc: dict[str, Any] = {
        "type": "FeatureCollection",
        "schema_version": PALMS_SCHEMA_VERSION,
        "region": region,
        "generated_at": stamp,
        "data_version": version,
        "generator": {"name": generator_name, "version": generator_version},
        "config_sha256": config_sha256,
        "features": [p.to_feature() for p in palms],
    }
    write_palms_doc(path, doc)
    return PalmsMeta(
        schema_version=PALMS_SCHEMA_VERSION,
        region=region,
        generated_at=stamp,
        data_version=version,
        generator_name=generator_name,
        generator_version=generator_version,
        config_sha256=config_sha256,
    )


# --- reading -----------------------------------------------------------------------------------


def _meta_from_doc(doc: Mapping[str, Any]) -> PalmsMeta:
    try:
        generator = doc["generator"]
        return PalmsMeta(
            schema_version=doc["schema_version"],
            region=doc["region"],
            generated_at=doc["generated_at"],
            data_version=doc["data_version"],
            generator_name=generator["name"],
            generator_version=generator["version"],
            config_sha256=doc["config_sha256"],
        )
    except (KeyError, TypeError) as exc:
        raise ContractError(f"palms.geojson is missing file metadata: {exc!r}") from exc


def read_palms(
    path: Path,
    *,
    validate: bool = True,
    region: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> PalmCollection:
    """Read and validate a palms.geojson file; palms are returned sorted by `palm_id`."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ContractError(f"cannot read {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ContractError(f"{path}: top-level JSON value must be an object")

    if validate:
        report = validate_palms(doc, mode="read", region=region, bbox=bbox)
        for issue in report.warnings:
            log.warning("%s: %s", path, issue)
        report.raise_for_errors()
    else:
        check_version(doc.get("schema_version"))  # type: ignore[arg-type]
        features = doc.get("features")
        report = ValidationReport(
            doc["schema_version"], len(features) if isinstance(features, list) else 0
        )

    meta = _meta_from_doc(doc)
    try:
        palms = sorted((Palm.from_feature(f) for f in doc["features"]), key=lambda p: p.palm_id)
    except (KeyError, TypeError, ValueError) as exc:
        raise ContractError(f"{path}: malformed feature: {exc!r}") from exc
    return PalmCollection(meta, palms, report)
