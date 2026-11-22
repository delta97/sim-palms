"""Validate palms.geojson and buildings.geojson documents against their schemas.

The checks run in this order: version, schema (envelope, then each feature), semantic rules S1-S9.
Schema problems are reported in a `ValidationReport`; only a malformed or unsupported
major version raises `ContractError`.
"""

from __future__ import annotations

import copy
import functools
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal, cast

from jsonschema import Draft202012Validator

from palmcore.errors import ContractError
from palmcore.schemas import load_schema, make_validator, schema_dir

PALMS_SCHEMA_VERSION: Final = "1.0"
SUPPORTED: Final = (1, 0)  # (major, newest minor this code knows)
BUILDINGS_SCHEMA_FILE: Final = "buildings.geojson.schema.json"

_VERSION_RE: Final = re.compile(r"^\d+\.\d+$")
_RADIUS_TOLERANCE: Final = 1e-6
_RELAXED_ENUM_FIELDS: Final = ("species_source", "height_source", "detected_by")

Severity = Literal["error", "warning"]
Mode = Literal["read", "write"]
VersionRelation = Literal["exact", "older_minor", "newer_minor"]


@dataclass(frozen=True)
class ValidationIssue:
    severity: Severity
    path: str  # "features[12].properties.height_m"; "" for file level
    message: str
    feature_index: int | None = None
    palm_id: str | None = None

    def __str__(self) -> str:
        if self.feature_index is None:
            return f"{self.severity} {self.path or 'file'}: {self.message}"
        prefix = f"features[{self.feature_index}]"
        label = f"{prefix} {self.palm_id}" if self.palm_id else prefix
        rest = self.path[len(prefix) :].lstrip(".") if self.path.startswith(prefix) else self.path
        if rest:
            return f"{self.severity} {label}: {rest}: {self.message}"
        return f"{self.severity} {label}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "path": self.path,
            "message": self.message,
            "feature_index": self.feature_index,
            "palm_id": self.palm_id,
        }


@dataclass
class ValidationReport:
    schema_version: str | None
    feature_count: int
    issues: list[ValidationIssue] = field(default_factory=list)
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def summary(self) -> str:
        text = (
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s) "
            f"in {self.feature_count} feature(s)"
        )
        return f"{text} (truncated)" if self.truncated else text

    def raise_for_errors(self) -> None:
        if self.errors:
            raise ContractError(self.summary(), self.errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "feature_count": self.feature_count,
            "ok": self.ok,
            "truncated": self.truncated,
            "issues": [i.to_dict() for i in self.issues],
        }

    def error_strings(self, limit: int = 20) -> list[str]:
        """The first `limit` errors as strings, for wrappers that return `list[str]`."""
        return [str(i) for i in self.errors[:limit]]


def parse_version(text: str) -> tuple[int, int]:
    if not isinstance(text, str) or not _VERSION_RE.match(text):
        raise ValueError(f"malformed schema version: {text!r} (expected MAJOR.MINOR)")
    major, minor = text.split(".")
    return int(major), int(minor)


def _relation(found: object, label: str) -> VersionRelation:
    if not isinstance(found, str):
        raise ContractError(f"{label} schema_version must be a string, got {found!r}")
    try:
        major, minor = parse_version(found)
    except ValueError as exc:
        raise ContractError(f"{label} schema_version is malformed: {found!r}") from exc
    if major != SUPPORTED[0]:
        raise ContractError(
            f"{label} schema {found} is not supported (this palmcore reads {SUPPORTED[0]}.x); "
            "rerun palmscan or update palmfix"
        )
    if minor == SUPPORTED[1]:
        return "exact"
    return "older_minor" if minor < SUPPORTED[1] else "newer_minor"


def check_version(found: str) -> VersionRelation:
    """Classify a palms schema version; ContractError if malformed or another major."""
    return _relation(found, "palms.geojson")


# --- schema handling -------------------------------------------------------------------------


def _feature_validator(schema: Mapping[str, Any]) -> Draft202012Validator:
    sub = {
        "$schema": schema.get("$schema"),
        "$defs": schema["$defs"],
        "$ref": "#/$defs/feature",
    }
    return make_validator(sub)


def _relax(schema: Mapping[str, Any]) -> dict[str, Any]:
    relaxed = copy.deepcopy(dict(schema))
    props = relaxed["$defs"]["feature"]["properties"]["properties"]
    props["additionalProperties"] = True
    for name in _RELAXED_ENUM_FIELDS:
        props["properties"][name] = {"type": "string"}
    return relaxed


@dataclass(frozen=True)
class _Compiled:
    envelope: Draft202012Validator
    feature: Draft202012Validator


@functools.cache
def _palms_validators(relaxed: bool) -> _Compiled:
    schema = load_schema("palms")
    if relaxed:
        schema = _relax(schema)
    return _Compiled(make_validator(schema), _feature_validator(schema))


@functools.cache
def _buildings_validators() -> _Compiled:
    path = schema_dir() / BUILDINGS_SCHEMA_FILE
    schema = cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
    return _Compiled(make_validator(schema), _feature_validator(schema))


def _path_text(prefix: str, parts: Iterable[Any]) -> str:
    out = prefix
    for part in parts:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


class _Collector:
    """Accumulates issues and enforces the max_errors cap."""

    def __init__(self, max_errors: int) -> None:
        self.issues: list[ValidationIssue] = []
        self.max_errors = max_errors
        self.error_count = 0
        self.truncated = False

    def add(self, issue: ValidationIssue) -> bool:
        if issue.severity == "error":
            if self.error_count >= self.max_errors:
                self.truncated = True
                return False
            self.error_count += 1
        self.issues.append(issue)
        return True

    def error(
        self, path: str, message: str, index: int | None = None, palm_id: str | None = None
    ) -> bool:
        return self.add(ValidationIssue("error", path, message, index, palm_id))

    def warning(
        self, path: str, message: str, index: int | None = None, palm_id: str | None = None
    ) -> bool:
        return self.add(ValidationIssue("warning", path, message, index, palm_id))


def _palm_id_of(feature: Any) -> str | None:
    if isinstance(feature, Mapping):
        props = feature.get("properties")
        if isinstance(props, Mapping) and isinstance(props.get("palm_id"), str):
            return cast("str", props["palm_id"])
    return None


def _check_envelope(
    validator: Draft202012Validator, doc: Mapping[str, Any], out: _Collector
) -> None:
    features = doc.get("features")
    envelope = {**doc, "features": []} if isinstance(features, list) else dict(doc)
    errors = sorted(validator.iter_errors(envelope), key=lambda e: _path_text("", e.absolute_path))
    for err in errors:
        out.error(_path_text("", err.absolute_path).lstrip("."), err.message)


def _check_features(
    validator: Draft202012Validator,
    features: list[Any],
    out: _Collector,
    id_of: Callable[[Any], str | None],
) -> set[int]:
    """Schema-check each feature; return the indexes that passed."""
    clean: set[int] = set()
    for index, feature in enumerate(features):
        errors = sorted(
            validator.iter_errors(feature),
            key=lambda e: (_path_text("", e.absolute_path), e.message),
        )
        if not errors:
            clean.add(index)
            continue
        palm_id = id_of(feature)
        prefix = f"features[{index}]"
        for err in errors:
            if not out.error(_path_text(prefix, err.absolute_path), err.message, index, palm_id):
                return clean  # capped; stop early
    return clean


# --- palms -----------------------------------------------------------------------------------


def _check_feature_semantics(
    index: int,
    feature: Mapping[str, Any],
    file_region: object,
    bbox: tuple[float, float, float, float] | None,
    out: _Collector,
) -> bool:
    """S2 (feature region), S4-S8 for one schema-clean feature. False when capped."""
    props = feature["properties"]
    palm_id: str = props["palm_id"]
    base = f"features[{index}]"

    def err(sub: str, message: str) -> bool:
        return out.error(f"{base}.{sub}", message, index, palm_id)

    if isinstance(file_region, str) and props["region"] != file_region:
        message = f"region {props['region']!r} does not match file region {file_region!r}"
        if not err("properties.region", message):
            return False
    if "id" in feature and feature["id"] != palm_id:
        message = f"id {feature['id']!r} does not equal palm_id {palm_id!r}"
        if not err("id", message):
            return False
    if bbox is not None:
        lon, lat = feature["geometry"]["coordinates"]
        min_lon, min_lat, max_lon, max_lat = bbox
        inside = min_lon <= lon <= max_lon and min_lat <= lat <= max_lat
        message = f"point [{lon}, {lat}] is outside bbox {list(bbox)}"
        if not inside and not err("geometry.coordinates", message):
            return False
    if props["exclusion_radius_m"] < props["crown_diam_m"] / 2 - _RADIUS_TOLERANCE:
        message = (
            f"exclusion_radius_m {props['exclusion_radius_m']} is less than half of "
            f"crown_diam_m {props['crown_diam_m']}"
        )
        if not err("properties.exclusion_radius_m", message):
            return False
    detected = props["detected_by"].split("+")
    for source_field, needed in (
        ("height_source", "lidar"),
        ("species_source", "inventory"),
        ("species_source", "osm"),
    ):
        if props[source_field] == needed and needed not in detected:
            message = (
                f"{source_field} is {needed!r} but detected_by {props['detected_by']!r} "
                f"does not include {needed!r}"
            )
            if not err("properties.detected_by", message):
                return False
    if props["ground_elev_m"] is None and props["height_source"] == "lidar":
        out.warning(
            f"{base}.properties.ground_elev_m",
            "ground_elev_m is null while height_source is 'lidar'",
            index,
            palm_id,
        )
    return True


def _semantic_checks(
    doc: Mapping[str, Any],
    features: list[Any],
    clean: set[int],
    out: _Collector,
    region: str | None,
    bbox: tuple[float, float, float, float] | None,
) -> None:
    file_region = doc.get("region")
    if region is not None and file_region != region:
        out.error("region", f"file region {file_region!r} does not match expected {region!r}")

    seen: dict[str, int] = {}
    prefixes: set[str] = set()
    for index in sorted(clean):
        feature = features[index]
        palm_id: str = feature["properties"]["palm_id"]
        if palm_id in seen:
            message = f"duplicate palm_id (first seen at features[{seen[palm_id]}])"
            if not out.error(f"features[{index}].properties.palm_id", message, index, palm_id):
                return
        else:
            seen[palm_id] = index
        prefixes.add(palm_id.split("-", 1)[0])
        if not _check_feature_semantics(index, feature, file_region, bbox, out):
            return
    if len(prefixes) > 1:
        out.error("features", f"palm_id prefixes are not identical: {sorted(prefixes)}")


def validate_palms(
    doc: Mapping[str, Any],
    *,
    mode: Mode = "read",
    region: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    max_errors: int = 100,
) -> ValidationReport:
    features_raw = doc.get("features")
    features: list[Any] = features_raw if isinstance(features_raw, list) else []
    version = doc.get("schema_version")
    if version is None:
        return ValidationReport(
            None,
            len(features),
            [ValidationIssue("error", "schema_version", "'schema_version' is a required property")],
        )
    relation = _relation(version, "palms.geojson")
    version_text = cast("str", version)

    out = _Collector(max_errors)
    relaxed = False
    if mode == "write":
        if version_text != PALMS_SCHEMA_VERSION:
            out.error(
                "schema_version",
                f"writers must write schema_version {PALMS_SCHEMA_VERSION!r}, got {version_text!r}",
            )
    elif relation == "newer_minor":
        relaxed = True
        out.warning(
            "schema_version",
            f"file is schema {version_text}, this palmcore knows {PALMS_SCHEMA_VERSION}; "
            "unknown fields ignored",
        )

    compiled = _palms_validators(relaxed)
    _check_envelope(compiled.envelope, doc, out)
    clean = _check_features(compiled.feature, features, out, _palm_id_of)
    if not out.truncated:
        _semantic_checks(doc, features, clean, out, region, bbox)
    if isinstance(features_raw, list) and not features:
        out.warning("features", "features is empty")
    return ValidationReport(version_text, len(features), out.issues, out.truncated)


def validate_palms_file(path: Path, **kwargs: Any) -> ValidationReport:
    """Like `validate_palms`, reading JSON from `path`. A parse failure is one error."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return ValidationReport(
            None, 0, [ValidationIssue("error", "", f"cannot read {path}: {exc}")]
        )
    if not isinstance(doc, dict):
        return ValidationReport(
            None, 0, [ValidationIssue("error", "", "top-level JSON value must be an object")]
        )
    return validate_palms(doc, **kwargs)


# --- buildings -------------------------------------------------------------------------------


def validate_buildings(doc: Mapping[str, Any], *, max_errors: int = 100) -> ValidationReport:
    features_raw = doc.get("features")
    features: list[Any] = features_raw if isinstance(features_raw, list) else []
    version = doc.get("schema_version")
    if version is None:
        return ValidationReport(
            None,
            len(features),
            [ValidationIssue("error", "schema_version", "'schema_version' is a required property")],
        )
    relation = _relation(version, "buildings.geojson")
    out = _Collector(max_errors)
    if relation == "newer_minor":
        out.warning(
            "schema_version",
            f"file is schema {version}, this palmcore knows {PALMS_SCHEMA_VERSION}; "
            "unknown fields ignored",
        )
    compiled = _buildings_validators()
    _check_envelope(compiled.envelope, doc, out)
    clean = _check_features(compiled.feature, features, out, lambda _feature: None)
    seen: dict[str, int] = {}
    for index in sorted(clean):
        building_id = features[index]["properties"]["building_id"]
        if building_id in seen:
            first = seen[building_id]
            message = f"duplicate building_id {building_id!r} (first seen at features[{first}])"
            if not out.error(f"features[{index}].properties.building_id", message, index):
                break
        else:
            seen[building_id] = index
    return ValidationReport(cast("str", version), len(features), out.issues, out.truncated)
