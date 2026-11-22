"""Asset manifest: species specs and library config in, ``assets/manifest.json`` out.

Contract and rules: ``plans/detailed/03-palm-assets.md`` (manifest contract, GUID policy,
naming conventions). The output is deterministic: sorted keys, no timestamps, no absolute paths.
"""

from __future__ import annotations

import itertools
import json
import re
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

import yaml

from palmcore.errors import ConfigError, ContractError
from palmcore.log import get_logger
from palmcore.paths import Paths
from palmcore.schemas import load_schema, make_validator

log = get_logger("assets.manifest")

MANIFEST_VERSION: Final = 1
NAMESPACE: Final = uuid.uuid5(uuid.NAMESPACE_DNS, "palmfix-assets.sim-palms.invalid")
GUID_PREFIX: Final = "palmfix-assets/"
DESIGN_DISTANCES_M: Final = (0, 150, 600, 2000)
MODEL_LIB_DIR: Final = "PackageSources/modelLib"
SCHEMA_NAME: Final = "asset-manifest.schema.json"
REGISTRY_REL_PATH: Final = "palmscan/data/species_keys.yaml"
PACKAGE_DEFINITION_REL: Final = "PackageDefinitions/palmfix-assets.xml"
DEFAULT_KEY: Final = "_default"

SPECIES_KEY_RE: Final = re.compile(r"^[a-z]+(_[a-z]+)+$")
VARIANT_RE: Final = re.compile(r"^(short|medium|tall)(_b)?$")
_SEMVER_RE: Final = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_SETS: Final = ("socal", "florida")
_STATUSES: Final = ("draft", "in_review", "accepted")


@dataclass(frozen=True)
class Lod:
    lod: int
    file: str
    triangles: int | None
    min_size: float | None
    design_distance_m: float


@dataclass(frozen=True)
class Variant:
    variant: str
    height_class: str
    alt: str | None
    model_name: str
    model_guid: str
    native_height_m: float | None
    crown_diam_m: float | None
    model_xml: str
    lods: tuple[Lod, ...]
    simobject_title: str


@dataclass(frozen=True)
class Species:
    key: str
    common_name: str
    set: str
    status: str
    lean_max_deg: float
    variants: tuple[Variant, ...]


@dataclass(frozen=True)
class ScaleLimits:
    min: float
    max: float


@dataclass(frozen=True)
class Manifest:
    manifest_version: int
    package_name: str
    package_version: str
    scale_limits: ScaleLimits
    species_fallback: Mapping[str, str]
    species: Mapping[str, Species]


@dataclass(frozen=True)
class Library:
    package_name: str
    package_version: str
    scale_limits: ScaleLimits
    species_fallback: Mapping[str, str]


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    native_height_m: float
    crown_diam_m: float


@dataclass(frozen=True)
class SpeciesSpec:
    species: str
    common_name: str
    set: str
    status: str
    lean_max_deg: float
    variants: tuple[VariantSpec, ...]


@dataclass(frozen=True)
class Measured:
    """Measured values for one model. ``None`` means "not measured": use the yaml target."""

    native_height_m: float | None = None
    crown_diam_m: float | None = None
    triangles: tuple[int | None, ...] | None = None
    min_sizes: tuple[float | None, ...] | None = None


Measure = Callable[[Path], Measured]


def not_measured(model_dir: Path) -> Measured:
    """Default measure function: nothing measured (ASSET-006 and ASSET-007 plug in real ones)."""
    return Measured()


# --- naming and GUIDs -------------------------------------------------------------------


def _check_species_key(species: str) -> None:
    if not SPECIES_KEY_RE.match(species):
        raise ValueError(f"invalid species key: {species!r}")


def _check_variant(variant: str) -> None:
    if not VARIANT_RE.match(variant):
        raise ValueError(f"invalid variant: {variant!r}")


def model_name(species: str, variant: str) -> str:
    """``palmfix_<species_key>_<variant>``."""
    _check_species_key(species)
    _check_variant(variant)
    return f"palmfix_{species}_{variant}"


def model_guid(name: str) -> str:
    """Deterministic model GUID: lowercase uuid5, no braces."""
    return str(uuid.uuid5(NAMESPACE, GUID_PREFIX + name))


def simobject_title(species: str, variant: str) -> str:
    """``PalmFix <Genus> <species> <Variant>``; ``_b`` becomes `` B``."""
    _check_species_key(species)
    _check_variant(variant)
    genus, *rest = species.split("_")
    base, _, alt = variant.partition("_")
    title = f"PalmFix {genus.capitalize()} {' '.join(rest)} {base.capitalize()}"
    return f"{title} {alt.upper()}" if alt else title


def _model_xml_path(species: str, name: str) -> str:
    return f"{MODEL_LIB_DIR}/{species}/{name}/{name}.xml"


# --- yaml inputs ------------------------------------------------------------------------


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc


def _mapping(value: Any, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: expected a mapping")
    return cast("dict[str, Any]", value)


def _number(value: Any, where: str, *, positive: bool = True) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"{where}: expected a number, got {value!r}")
    if positive and value <= 0:
        raise ConfigError(f"{where}: must be > 0, got {value!r}")
    return float(value)


def load_library(assets_dir: Path) -> Library:
    """Read ``<assets_dir>/library.yaml``."""
    path = assets_dir / "library.yaml"
    data = _mapping(_read_yaml(path), str(path))
    name = data.get("package_name")
    version = data.get("package_version")
    if not isinstance(name, str) or not name:
        raise ConfigError(f"{path}: package_name must be a non-empty string")
    if not isinstance(version, str) or not _SEMVER_RE.match(version):
        raise ConfigError(f"{path}: package_version must be a semver string like 0.1.0")
    limits = _mapping(data.get("scale_limits"), f"{path}: scale_limits")
    lo = _number(limits.get("min"), f"{path}: scale_limits.min")
    hi = _number(limits.get("max"), f"{path}: scale_limits.max")
    if lo > hi:
        raise ConfigError(f"{path}: scale_limits.min {lo} is above max {hi}")
    fallback_raw = _mapping(data.get("species_fallback", {}), f"{path}: species_fallback")
    fallback: dict[str, str] = {}
    for key, target in fallback_raw.items():
        if key != DEFAULT_KEY and not SPECIES_KEY_RE.match(str(key)):
            raise ConfigError(f"{path}: species_fallback key {key!r} is not a species key")
        if not isinstance(target, str) or not SPECIES_KEY_RE.match(target):
            raise ConfigError(f"{path}: species_fallback target for {key!r} is not a species key")
        fallback[str(key)] = target
    return Library(name, version, ScaleLimits(lo, hi), fallback)


def _parse_species(path: Path) -> SpeciesSpec:
    data = _mapping(_read_yaml(path), str(path))
    key = data.get("species")
    if not isinstance(key, str) or not SPECIES_KEY_RE.match(key):
        raise ConfigError(f"{path}: species must be a key like genus_species, got {key!r}")
    if path.stem != key:
        raise ConfigError(f"{path}: file name must be {key}.yaml")
    common = data.get("common_name")
    if not isinstance(common, str) or not common:
        raise ConfigError(f"{path}: common_name must be a non-empty string")
    set_ = data.get("set")
    if set_ not in _SETS:
        raise ConfigError(f"{path}: set must be one of {_SETS}, got {set_!r}")
    status = data.get("status")
    if status not in _STATUSES:
        raise ConfigError(f"{path}: status must be one of {_STATUSES}, got {status!r}")
    lean = _number(data.get("lean_max_deg", 0), f"{path}: lean_max_deg", positive=False)
    if not 0 <= lean <= 45:
        raise ConfigError(f"{path}: lean_max_deg must be between 0 and 45")
    raw_variants = data.get("variants")
    if not isinstance(raw_variants, list) or not raw_variants:
        raise ConfigError(f"{path}: variants must be a non-empty list")
    variants: list[VariantSpec] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_variants):
        item = _mapping(raw, f"{path}: variants[{i}]")
        name = item.get("variant")
        if not isinstance(name, str) or not VARIANT_RE.match(name):
            raise ConfigError(f"{path}: variants[{i}].variant {name!r} is not valid")
        if name in seen:
            raise ConfigError(f"{path}: duplicate variant {name!r}")
        seen.add(name)
        variants.append(
            VariantSpec(
                name,
                _number(item.get("native_height_m"), f"{path}: variants[{i}].native_height_m"),
                _number(item.get("crown_diam_m"), f"{path}: variants[{i}].crown_diam_m"),
            )
        )
    return SpeciesSpec(key, common, set_, status, lean, tuple(variants))


def load_species_specs(assets_dir: Path) -> dict[str, SpeciesSpec]:
    """Read every ``<assets_dir>/species/*.yaml``, keyed by species key (sorted)."""
    specs: dict[str, SpeciesSpec] = {}
    for path in sorted((assets_dir / "species").glob("*.yaml")):
        spec = _parse_species(path)
        specs[spec.species] = spec
    return specs


# --- generation -------------------------------------------------------------------------


def _compact(value: float) -> float:
    """Integral values print as ``5``, not ``5.0``."""
    return int(value) if float(value).is_integer() else value


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 2)


def _variant_entry(
    spec: SpeciesSpec, vs: VariantSpec, assets_dir: Path, measure: Measure
) -> dict[str, Any]:
    name = model_name(spec.species, vs.variant)
    model_dir = assets_dir / MODEL_LIB_DIR / spec.species / name
    m = measure(model_dir)
    height_class, _, alt = vs.variant.partition("_")
    tris = m.triangles or (None,) * 4
    mins = m.min_sizes or (None,) * 4
    if len(tris) != 4 or len(mins) != 4:
        raise ContractError(f"{name}: measure() must return exactly 4 LOD values")
    lods = [
        {
            "lod": n,
            "file": f"{name}_LOD{n}.gltf",
            "triangles": tris[n],
            "min_size": mins[n],
            "design_distance_m": DESIGN_DISTANCES_M[n],
        }
        for n in range(4)
    ]
    height = m.native_height_m if m.native_height_m is not None else vs.native_height_m
    crown = m.crown_diam_m if m.crown_diam_m is not None else vs.crown_diam_m
    return {
        "variant": vs.variant,
        "height_class": height_class,
        "alt": alt or None,
        "model_name": name,
        "model_guid": model_guid(name),
        "native_height_m": _round(height),
        "crown_diam_m": _round(crown),
        "model_xml": _model_xml_path(spec.species, name),
        "lods": lods,
        "simobject_title": simobject_title(spec.species, vs.variant),
    }


def build_manifest(
    assets_dir: Path, measure: Measure | None = None, *, include_draft: bool = False
) -> dict[str, Any]:
    """Build the manifest dict from ``library.yaml`` and ``species/*.yaml``.

    ``measure`` takes a model directory and returns :class:`Measured` stats; the default
    reports nothing, so yaml targets are used. Draft species are left out unless
    ``include_draft`` (preview manifests only).
    """
    measure_fn = measure or not_measured
    library = load_library(assets_dir)
    species: dict[str, Any] = {}
    for key, spec in load_species_specs(assets_dir).items():
        if spec.status == "draft" and not include_draft:
            continue
        ordered = sorted(spec.variants, key=lambda v: (v.native_height_m, v.variant))
        species[key] = {
            "common_name": spec.common_name,
            "set": spec.set,
            "status": spec.status,
            "lean_max_deg": _compact(spec.lean_max_deg),
            "variants": [_variant_entry(spec, v, assets_dir, measure_fn) for v in ordered],
        }
    return {
        "manifest_version": MANIFEST_VERSION,
        "package_name": library.package_name,
        "package_version": library.package_version,
        "scale_limits": {
            "min": _compact(library.scale_limits.min),
            "max": _compact(library.scale_limits.max),
        },
        "species_fallback": dict(library.species_fallback),
        "species": species,
    }


def dump_manifest(manifest: Mapping[str, Any]) -> str:
    """Canonical text: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


# --- loading ----------------------------------------------------------------------------


def _read_manifest_json(path: Path) -> dict[str, Any]:
    try:
        return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"{path} is not valid JSON: {exc}") from exc


def _schema_errors(data: Any) -> list[str]:
    validator = make_validator(load_schema(SCHEMA_NAME))
    errors = sorted(validator.iter_errors(data), key=lambda e: [str(p) for p in e.absolute_path])
    return [
        "schema: " + "/".join(str(p) for p in e.absolute_path) + ": " + e.message for e in errors
    ]


def _lod_from_dict(d: Mapping[str, Any]) -> Lod:
    return Lod(d["lod"], d["file"], d["triangles"], d["min_size"], d["design_distance_m"])


def _variant_from_dict(v: Mapping[str, Any]) -> Variant:
    return Variant(
        variant=v["variant"],
        height_class=v["height_class"],
        alt=v["alt"],
        model_name=v["model_name"],
        model_guid=v["model_guid"],
        native_height_m=v["native_height_m"],
        crown_diam_m=v["crown_diam_m"],
        model_xml=v["model_xml"],
        lods=tuple(_lod_from_dict(d) for d in v["lods"]),
        simobject_title=v["simobject_title"],
    )


def _from_dict(data: Mapping[str, Any]) -> Manifest:
    species = {
        key: Species(
            key,
            s["common_name"],
            s["set"],
            s["status"],
            s["lean_max_deg"],
            tuple(_variant_from_dict(v) for v in s["variants"]),
        )
        for key, s in data["species"].items()
    }
    limits = data["scale_limits"]
    return Manifest(
        manifest_version=data["manifest_version"],
        package_name=data["package_name"],
        package_version=data["package_version"],
        scale_limits=ScaleLimits(limits["min"], limits["max"]),
        species_fallback=dict(data["species_fallback"]),
        species=species,
    )


def load_manifest(path: Path) -> Manifest:
    """Load and schema-check a manifest into typed objects. Raises ``ContractError``."""
    data = _read_manifest_json(path)
    errors = _schema_errors(data)
    if errors:
        raise ContractError(f"{path} does not match the manifest schema", issues=errors)
    return _from_dict(data)


# --- validation -------------------------------------------------------------------------


def _load_registry(path: Path) -> set[str]:
    """Species keys from ``species_keys.yaml``: a list, or a mapping with a list/mapping inside."""
    data = _read_yaml(path)
    if isinstance(data, dict):
        for name in ("species", "keys", "species_keys"):
            if name in data:
                data = data[name]
                break
    if isinstance(data, dict):
        return {str(k) for k in data}
    if isinstance(data, list):
        return {str(k["key"] if isinstance(k, dict) and "key" in k else k) for k in data}
    raise ConfigError(f"{path}: unrecognised species registry format")


def _package_definition_version(path: Path) -> str | None:
    # VERIFY (ASSET-004): where the 2024 package definition stores the version.
    # Accepts a `Version` attribute or a `<Version>` element.
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == "Version" and el.text and el.text.strip():
            return el.text.strip()
        if "Version" in el.attrib:
            return el.attrib["Version"]
    return None


def _variant_problems(key: str, v: Variant) -> list[str]:
    problems: list[str] = []
    expected_name = model_name(key, v.variant)
    if v.model_name != expected_name:
        problems.append(f"{key}/{v.variant}: model_name {v.model_name!r} != {expected_name!r}")
    if v.model_guid != model_guid(v.model_name):
        problems.append(
            f"{v.model_name}: model_guid {v.model_guid} != uuid5 of name "
            f"({model_guid(v.model_name)})"
        )
    if v.simobject_title != simobject_title(key, v.variant):
        problems.append(f"{v.model_name}: simobject_title {v.simobject_title!r} is wrong")
    if [lod.lod for lod in v.lods] != [0, 1, 2, 3]:
        problems.append(f"{v.model_name}: lods must be numbered 0 to 3 in order")
    counts = [lod.triangles for lod in v.lods]
    known = [c for c in counts if c is not None]
    if len(known) == len(counts) and any(a <= b for a, b in itertools.pairwise(known)):
        problems.append(f"{v.model_name}: lod triangles must strictly decrease: {known}")
    return problems


def validate_manifest(
    path: Path, *, registry_path: Path | None = None, assets_dir: Path | None = None
) -> list[str]:
    """Return a list of problems (empty means valid).

    Checks: schema, unique GUIDs, GUID == uuid5(name), model names and titles follow the
    naming rules, fallback targets exist, species keys are in the registry, and the package
    version matches the package definition if one exists (``assets_dir`` defaults to the
    manifest's folder).
    """
    data = _read_manifest_json(path)
    problems = _schema_errors(data)
    if problems:
        return problems  # later checks assume a well-formed document
    manifest = _from_dict(data)

    owner: dict[str, str] = {}
    for key, sp in manifest.species.items():
        seen_variants: set[str] = set()
        for v in sp.variants:
            problems.extend(_variant_problems(key, v))
            if v.model_guid in owner:
                problems.append(
                    f"duplicate model_guid {v.model_guid}: {owner[v.model_guid]} and {v.model_name}"
                )
            owner[v.model_guid] = v.model_name
            if v.variant in seen_variants:
                problems.append(f"{key}: duplicate variant {v.variant!r}")
            seen_variants.add(v.variant)
    if manifest.scale_limits.min > manifest.scale_limits.max:
        problems.append("scale_limits.min is above max")

    for src, target in manifest.species_fallback.items():
        if target not in manifest.species:
            problems.append(f"species_fallback {src} -> {target}: target is not in the manifest")

    reg_path = registry_path or Paths.resolve().repo_root / REGISTRY_REL_PATH
    if reg_path.is_file():
        registry = _load_registry(reg_path)
        used = set(manifest.species) | set(manifest.species_fallback.values())
        used |= {k for k in manifest.species_fallback if k != DEFAULT_KEY}
        problems.extend(
            f"species key {key!r} is not in the registry {reg_path.name}"
            for key in sorted(used - registry)
        )
    else:
        log.warning(
            "species registry %s not found; only the key pattern was checked "
            "(SCAN-002 not merged?)",
            reg_path,
        )

    definition = (assets_dir or path.parent) / PACKAGE_DEFINITION_REL
    if definition.is_file():
        found = _package_definition_version(definition)
        if found is not None and found != manifest.package_version:
            problems.append(
                f"package_version {manifest.package_version} != {found} in {PACKAGE_DEFINITION_REL}"
            )
    return problems
