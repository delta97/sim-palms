"""Region config: load ``regions/<name>.yaml`` into a frozen :class:`RegionConfig`.

Defaults are defined once, here. ``schemas/region.schema.json`` repeats them in ``default``
keywords and a test asserts the two agree. Every relative path in a region file resolves against
``base_dir`` (the repo root), so a loaded config only holds absolute paths.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final, Literal, cast

import pyproj
import yaml
from jsonschema import ValidationError

from palmcore.errors import ConfigError
from palmcore.geo import Bbox, local_crs_for
from palmcore.log import get_logger
from palmcore.schemas import load_schema, make_validator

logger = get_logger(__name__)

SUPPORTED_CONFIG_VERSIONS: Final = frozenset({1})

DEFAULT_OVERPASS_URL: Final = "https://overpass-api.de/api/interpreter"
DEFAULT_AIRPORT_MASK_PATH: Final = "docs/compat/airports-mask.geojson"
DEFAULT_LIDAR: Final = "none"
DEFAULT_BUILDINGS: Final = "none"
DEFAULT_HEIGHT_UNITS: Final = "ft"
DEFAULT_ARCGIS_WHERE: Final = "1=1"
DEFAULT_MASK_KIND: Final = "other"

_SLUG_RE: Final = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_ID_PREFIX_RE: Final = re.compile(r"^[a-z]{2,6}$")
_REQUIRED_RE: Final = re.compile(r"^'(.*)' is a required property$")


def _freeze(value: Mapping[str, Any]) -> Mapping[str, Any]:
    return MappingProxyType(copy.deepcopy(dict(value)))


@dataclass(frozen=True)
class InventorySource:
    """One tree inventory source."""

    name: str
    type: Literal["arcgis_rest", "geojson_file"]
    url: str | None
    path: Path | None
    format: Literal["geojson", "csv"] | None
    species_field: str
    common_name_field: str | None
    id_field: str | None
    status_field: str | None
    height_field: str | None
    height_units: Literal["ft", "m"]
    dbh_field: str | None
    date_field: str | None
    lon_field: str | None
    lat_field: str | None
    where: str | None
    vintage: str | None
    license: str | None
    cache_max_age_days: float | None
    options: Mapping[str, Any]


@dataclass(frozen=True)
class TypedSource:
    """A LiDAR or building source: a type name plus free-form options."""

    type: str
    options: Mapping[str, Any]


@dataclass(frozen=True)
class Sources:
    inventory: tuple[InventorySource, ...]
    lidar: TypedSource
    buildings: TypedSource
    buildings_path: Path | None
    overpass_url: str
    osm_trees: bool


@dataclass(frozen=True)
class ExclusionConfig:
    margin_m: float = 1.5
    polygon_sides: int = 12
    merge_gap_m: float = 2.0
    clip_buildings: bool = True
    clip_buffer_m: float = 0.3
    min_part_area_m2: float = 1.0
    radius_min_m: float = 1.0
    radius_max_m: float = 8.0
    default_radius_m: float = 3.0
    max_cluster_extent_m: float = 150.0
    max_vertices: int = 256


@dataclass(frozen=True)
class PlacementConfig:
    # Optional per-region override. The asset manifest owns scale limits (ASSET-005,
    # plans/detailed/03-palm-assets.md "Scale limits and species fallback"); None = no override.
    scale_clamp: float | None = None


@dataclass(frozen=True)
class MaskArea:
    name: str
    kind: Literal["mod", "airport", "other"]
    bbox: Bbox | None
    geometry: Mapping[str, Any] | None
    path: Path | None
    note: str | None


@dataclass(frozen=True)
class AirportMasks:
    enabled: bool = True
    buffer_m: float = 100.0
    # None only on a hand-built instance; the loader always fills the absolute default path.
    path: Path | None = None


@dataclass(frozen=True)
class RegionConfig:
    config_version: int
    region: str
    id_prefix: str
    name: str
    bbox: Bbox
    local_crs: str | None
    sources: Sources
    species_priors: Mapping[str, float]
    exclusion: ExclusionConfig
    placement: PlacementConfig
    mask_out: tuple[MaskArea, ...]
    airport_masks: AirportMasks
    palmscan: Mapping[str, Any]
    palmgen: Mapping[str, Any]
    raw: Mapping[str, Any]
    source_path: Path | None
    sha256: str

    def crs(self) -> str:
        """Metric CRS for this region: ``local_crs`` if set, else the UTM zone of the bbox."""
        return local_crs_for(self.bbox, self.local_crs)

    def to_dict(self) -> dict[str, Any]:
        """Normalised mapping with defaults applied and paths as strings (loadable again)."""
        return {
            "config_version": self.config_version,
            "region": self.region,
            "id_prefix": self.id_prefix,
            "name": self.name,
            "bbox": self.bbox.to_list(),
            "local_crs": self.local_crs,
            "sources": {
                "inventory": [_inventory_to_dict(s) for s in self.sources.inventory],
                "lidar": _typed_to_dict(self.sources.lidar),
                "buildings": _typed_to_dict(self.sources.buildings),
                "buildings_path": _path_str(self.sources.buildings_path),
                "overpass_url": self.sources.overpass_url,
                "osm_trees": self.sources.osm_trees,
            },
            "species_priors": dict(self.species_priors),
            "exclusion": {
                name: getattr(self.exclusion, name) for name in ExclusionConfig.__dataclass_fields__
            },
            "placement": {"scale_clamp": self.placement.scale_clamp},
            "mask_out": [_mask_to_dict(m) for m in self.mask_out],
            "masks": {
                "airports": {
                    "enabled": self.airport_masks.enabled,
                    "buffer_m": self.airport_masks.buffer_m,
                    "path": _path_str(self.airport_masks.path),
                }
            },
            "palmscan": copy.deepcopy(dict(self.palmscan)),
            "palmgen": copy.deepcopy(dict(self.palmgen)),
        }


def _path_str(path: Path | None) -> str | None:
    return None if path is None else str(path)


def _typed_to_dict(source: TypedSource) -> dict[str, Any]:
    return {"type": source.type, "options": copy.deepcopy(dict(source.options))}


def _inventory_to_dict(src: InventorySource) -> dict[str, Any]:
    out: dict[str, Any] = {"name": src.name, "type": src.type}
    if src.url is not None:
        out["url"] = src.url
    if src.path is not None:
        out["path"] = str(src.path)
    if src.format is not None:
        out["format"] = src.format
    out.update(
        species_field=src.species_field,
        common_name_field=src.common_name_field,
        id_field=src.id_field,
        status_field=src.status_field,
        height_field=src.height_field,
        height_units=src.height_units,
        dbh_field=src.dbh_field,
        date_field=src.date_field,
        lon_field=src.lon_field,
        lat_field=src.lat_field,
    )
    if src.where is not None:
        out["where"] = src.where
    out.update(
        vintage=src.vintage,
        license=src.license,
        cache_max_age_days=src.cache_max_age_days,
        options=copy.deepcopy(dict(src.options)),
    )
    return out


def _mask_to_dict(mask: MaskArea) -> dict[str, Any]:
    out: dict[str, Any] = {"name": mask.name, "kind": mask.kind}
    if mask.bbox is not None:
        out["bbox"] = mask.bbox.to_list()
    if mask.geometry is not None:
        out["geometry"] = copy.deepcopy(dict(mask.geometry))
    if mask.path is not None:
        out["path"] = str(mask.path)
    if mask.note is not None:
        out["note"] = mask.note
    return out


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate mapping keys and keeps date-like text as strings."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        self.flatten_mapping(node)
        seen: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in seen
                seen.add(key)
            except TypeError:
                continue  # unhashable key: the base class raises a proper error
            if duplicate:
                raise ConfigError(f"line {key_node.start_mark.line + 1}: duplicate key {key!r}")
        return super().construct_mapping(node, deep=deep)


# Region files hold vintages such as 2020-05-01; they must stay text, not become dates.
_UniqueKeyLoader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _label(source_path: Path | None) -> str:
    return str(source_path) if source_path is not None else "<region config>"


def _dotted(path: list[Any]) -> str:
    out = ""
    for part in path:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out or "<root>"


def _schema_problems(data: Mapping[str, Any]) -> list[str]:
    validator = make_validator(load_schema("region"))
    errors = sorted(
        validator.iter_errors(dict(data)),
        key=lambda e: ([str(p) for p in e.absolute_path], e.message),
    )
    lines: set[str] = set()
    for err in errors:
        path = list(err.absolute_path)
        lines.add(_describe(err, path))
    return sorted(lines)


def _describe(err: ValidationError, path: list[Any]) -> str:
    if err.validator == "required":
        match = _REQUIRED_RE.match(err.message)
        if match:
            return f"{_dotted([*path, match.group(1)])}: {err.message}"
    if err.validator == "additionalProperties" and isinstance(err.instance, dict):
        schema = cast("Mapping[str, Any]", err.schema)
        known = schema.get("properties", {})
        extras = [k for k in err.instance if k not in known]
        if extras:
            return "; ".join(
                f"{_dotted([*path, k])}: unknown key {k!r} (not allowed here)" for k in extras
            )
    if err.validator in ("oneOf", "anyOf", "not"):
        description = cast("Mapping[str, Any]", err.schema).get("description")
        if description:
            return f"{_dotted(path)}: {description}"
    return f"{_dotted(path)}: {err.message}"


def _raise(label: str, problems: list[str]) -> None:
    raise ConfigError("\n".join(f"{label}: {p}" for p in problems))


def _derive_id_prefix(region: str) -> str | None:
    parts = region.split("-")
    initials = "".join(m.group(0) for p in parts if (m := re.search(r"[a-z]", p)))
    if len(initials) < 2:
        # Single-word slugs: first letters of the slug.
        initials = re.sub(r"[^a-z]", "", region)[:3]
    initials = initials[:6]
    return initials if _ID_PREFIX_RE.match(initials) else None


def _abs_path(value: str, base_dir: Path) -> Path:
    p = Path(value)
    return Path(os.path.normpath(p if p.is_absolute() else base_dir / p))


def _opt_path(value: str | None, base_dir: Path) -> Path | None:
    return None if value is None else _abs_path(value, base_dir)


def _str_or_none(item: Mapping[str, Any], key: str) -> str | None:
    value = item.get(key)
    return None if value is None else str(value)


def _typed_source(value: Any, default: str) -> TypedSource:
    if value is None:
        return TypedSource(default, MappingProxyType({}))
    if isinstance(value, str):
        return TypedSource(value, MappingProxyType({}))
    return TypedSource(str(value["type"]), _freeze(value.get("options", {})))


def _resolve_format(item: Mapping[str, Any]) -> str | None:
    if item["type"] != "geojson_file":
        return None
    if "format" in item:
        return cast("str", item["format"])
    location = item.get("path") or urllib.parse.urlparse(item["url"]).path
    return "csv" if str(location).lower().endswith(".csv") else "geojson"


def _build_inventory(
    items: list[Mapping[str, Any]], base_dir: Path, problems: list[str]
) -> tuple[InventorySource, ...]:
    out: list[InventorySource] = []
    seen: dict[str, int] = {}
    for i, item in enumerate(items):
        where = f"sources.inventory[{i}]"
        name = cast("str", item["name"])
        if name in seen:
            problems.append(
                f"{where}.name: duplicate inventory name {name!r} (also [{seen[name]}])"
            )
        seen.setdefault(name, i)
        fmt = _resolve_format(item)
        lon, lat = _str_or_none(item, "lon_field"), _str_or_none(item, "lat_field")
        if fmt == "csv":
            for key, val in (("lon_field", lon), ("lat_field", lat)):
                if val is None:
                    problems.append(f"{where}.{key}: required when the source format is csv")
        is_arcgis = item["type"] == "arcgis_rest"
        age = item.get("cache_max_age_days")
        out.append(
            InventorySource(
                name=name,
                type=cast("Literal['arcgis_rest', 'geojson_file']", item["type"]),
                url=_str_or_none(item, "url"),
                path=_opt_path(_str_or_none(item, "path"), base_dir),
                format=cast("Literal['geojson', 'csv'] | None", fmt),
                species_field=cast("str", item["species_field"]),
                common_name_field=_str_or_none(item, "common_name_field"),
                id_field=_str_or_none(item, "id_field"),
                status_field=_str_or_none(item, "status_field"),
                height_field=_str_or_none(item, "height_field"),
                height_units=cast(
                    "Literal['ft', 'm']", item.get("height_units", DEFAULT_HEIGHT_UNITS)
                ),
                dbh_field=_str_or_none(item, "dbh_field"),
                date_field=_str_or_none(item, "date_field"),
                lon_field=lon,
                lat_field=lat,
                where=cast("str", item.get("where", DEFAULT_ARCGIS_WHERE if is_arcgis else None)),
                vintage=_str_or_none(item, "vintage"),
                license=_str_or_none(item, "license"),
                cache_max_age_days=None if age is None else float(age),
                options=_freeze(item.get("options", {})),
            )
        )
    return tuple(out)


def _build_masks(
    items: list[Mapping[str, Any]], base_dir: Path, region_bbox: Bbox | None, problems: list[str]
) -> tuple[MaskArea, ...]:
    out: list[MaskArea] = []
    seen: dict[str, int] = {}
    for i, item in enumerate(items):
        where = f"mask_out[{i}]"
        name = cast("str", item["name"])
        if name in seen:
            problems.append(f"{where}.name: duplicate mask name {name!r} (also [{seen[name]}])")
        seen.setdefault(name, i)
        bbox: Bbox | None = None
        if "bbox" in item:
            try:
                bbox = Bbox.from_list(item["bbox"])
            except ValueError as exc:
                problems.append(f"{where}.bbox: {exc}")
            else:
                if region_bbox is not None and not bbox.intersects(region_bbox):
                    logger.warning("mask %r bbox lies entirely outside the region bbox", name)
        geometry = item.get("geometry")
        out.append(
            MaskArea(
                name=name,
                kind=cast(
                    "Literal['mod', 'airport', 'other']", item.get("kind", DEFAULT_MASK_KIND)
                ),
                bbox=bbox,
                geometry=None if geometry is None else _freeze(geometry),
                path=_opt_path(_str_or_none(item, "path"), base_dir),
                note=_str_or_none(item, "note"),
            )
        )
    return tuple(out)


def _build(
    data: Mapping[str, Any],
    *,
    base_dir: Path,
    source_path: Path | None,
    expected_name: str | None,
    digest: str,
) -> RegionConfig:
    label = _label(source_path)
    base_dir = base_dir.resolve()

    version = data.get("config_version")
    if isinstance(version, bool) or version not in SUPPORTED_CONFIG_VERSIONS:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_CONFIG_VERSIONS))
        shown = "missing" if "config_version" not in data else repr(version)
        _raise(label, [f"config_version: {shown} is not supported (supported: {supported})"])

    problems = _schema_problems(data)
    if problems:
        _raise(label, problems)

    region = cast("str", data["region"])
    if expected_name is not None and region != expected_name:
        problems.append(f"region: {region!r} must equal the file name {expected_name!r}")

    bbox: Bbox | None = None
    try:
        bbox = Bbox.from_list(data["bbox"])
    except ValueError as exc:
        problems.append(f"bbox: {exc}")

    local_crs = cast("str | None", data.get("local_crs"))
    if local_crs is not None:
        try:
            pyproj.CRS.from_user_input(local_crs)
        except pyproj.exceptions.CRSError as exc:
            problems.append(f"local_crs: not a valid CRS: {exc}")

    id_prefix = cast("str | None", data.get("id_prefix")) or _derive_id_prefix(region)
    if id_prefix is None:
        problems.append("id_prefix: cannot derive a prefix from the region name; set it explicitly")

    priors = _normalise_priors(
        cast("Mapping[str, float]", data.get("species_priors", {})), problems
    )

    exclusion_in = cast("Mapping[str, Any]", data.get("exclusion", {}))
    defaults = ExclusionConfig()
    exclusion = ExclusionConfig(
        **{
            name: type(getattr(defaults, name))(exclusion_in.get(name, getattr(defaults, name)))
            for name in ExclusionConfig.__dataclass_fields__
        }
    )
    if exclusion.radius_min_m > exclusion.radius_max_m:
        problems.append(
            f"exclusion.radius_min_m: {exclusion.radius_min_m} is greater than "
            f"radius_max_m ({exclusion.radius_max_m})"
        )

    sources_in = cast("Mapping[str, Any]", data.get("sources", {}))
    inventory = _build_inventory(list(sources_in.get("inventory", [])), base_dir, problems)
    masks = _build_masks(list(data.get("mask_out", [])), base_dir, bbox, problems)

    airports_in = cast("Mapping[str, Any]", data.get("masks", {})).get("airports", {})
    airport_defaults = AirportMasks()
    airports = AirportMasks(
        enabled=bool(airports_in.get("enabled", airport_defaults.enabled)),
        buffer_m=float(airports_in.get("buffer_m", airport_defaults.buffer_m)),
        path=_abs_path(airports_in.get("path", DEFAULT_AIRPORT_MASK_PATH), base_dir),
    )

    if problems:
        _raise(label, problems)
    assert bbox is not None
    assert id_prefix is not None

    sources = Sources(
        inventory=inventory,
        lidar=_typed_source(sources_in.get("lidar"), DEFAULT_LIDAR),
        buildings=_typed_source(sources_in.get("buildings"), DEFAULT_BUILDINGS),
        buildings_path=_opt_path(cast("str | None", sources_in.get("buildings_path")), base_dir),
        overpass_url=cast("str", sources_in.get("overpass_url", DEFAULT_OVERPASS_URL)),
        osm_trees=bool(sources_in.get("osm_trees", False)),
    )
    return RegionConfig(
        config_version=cast("int", version),
        region=region,
        id_prefix=id_prefix,
        name=cast("str", data.get("name", region)),
        bbox=bbox,
        local_crs=local_crs,
        sources=sources,
        species_priors=MappingProxyType(priors),
        exclusion=exclusion,
        placement=_placement_config(cast("Mapping[str, Any]", data.get("placement", {}))),
        mask_out=masks,
        airport_masks=airports,
        palmscan=_freeze(cast("Mapping[str, Any]", data.get("palmscan", {}))),
        palmgen=_freeze(cast("Mapping[str, Any]", data.get("palmgen", {}))),
        raw=_freeze(data),
        source_path=source_path,
        sha256=digest,
    )


def _normalise_priors(priors: Mapping[str, float], problems: list[str]) -> dict[str, float]:
    if not priors:
        return {}
    total = float(sum(priors.values()))
    if total <= 0:
        problems.append("species_priors: values must sum to more than 0")
        return {}
    if abs(total - 1.0) < 1e-12:
        return {k: float(v) for k, v in priors.items()}
    return {k: float(v) / total for k, v in priors.items()}


def _parse_yaml(raw: bytes, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ConfigError(f"{label}: not valid UTF-8: {exc}") from exc
    try:
        data = yaml.load(text, Loader=_UniqueKeyLoader)
    except ConfigError as exc:
        raise ConfigError(f"{label}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"{label}: invalid YAML: {exc}") from exc
    if data is None:
        raise ConfigError(f"{label}: file is empty")
    if not isinstance(data, dict):
        raise ConfigError(f"{label}: top level must be a mapping, got {type(data).__name__}")
    return cast("dict[str, Any]", data)


def load_region_dict(
    data: Mapping[str, Any],
    *,
    base_dir: Path,
    source_path: Path | None = None,
    expected_name: str | None = None,
) -> RegionConfig:
    """Validate and build a config from an already-parsed mapping.

    ``sha256`` is the hash of the mapping's canonical JSON, since there are no file bytes.
    """
    canonical = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    return _build(
        data,
        base_dir=Path(base_dir),
        source_path=source_path,
        expected_name=expected_name,
        digest=hashlib.sha256(canonical).hexdigest(),
    )


def load_region(
    name_or_path: str | Path,
    *,
    regions_dir: Path | None = None,
    base_dir: Path | None = None,
) -> RegionConfig:
    """Load a region by file path (ends in ``.yaml``/``.yml``) or by slug.

    A slug needs ``regions_dir`` and resolves to ``regions_dir/<slug>.yaml``. ``base_dir``
    defaults to the parent of the directory holding the file.
    """
    value = str(name_or_path)
    if value.lower().endswith((".yaml", ".yml")):
        path = Path(value)
    else:
        if not _SLUG_RE.match(value):
            raise ConfigError(f"invalid region name {value!r}: use lowercase letters, digits, '-'")
        if regions_dir is None:
            raise ConfigError(f"regions_dir is required to load region {value!r} by name")
        path = Path(regions_dir) / f"{value}.yaml"
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"{path}: cannot read region file: {exc}") from exc
    data = _parse_yaml(raw, str(path))
    root = Path(base_dir) if base_dir is not None else path.resolve().parent.parent
    return _build(
        data,
        base_dir=root,
        source_path=path,
        expected_name=path.stem,
        digest=hashlib.sha256(raw).hexdigest(),
    )


def list_regions(regions_dir: Path) -> list[str]:
    """Sorted stems of ``*.yaml`` files in ``regions_dir``, skipping names starting with ``_``."""
    directory = Path(regions_dir)
    if not directory.is_dir():
        raise ConfigError(f"regions directory not found: {directory}")
    return sorted(
        p.stem for p in directory.glob("*.yaml") if p.is_file() and not p.name.startswith("_")
    )


def check_regions(regions_dir: Path) -> list[str]:
    """Load every region file; return all problems, including a shared ``id_prefix``."""
    errors: list[str] = []
    prefixes: dict[str, list[Path]] = {}
    for stem in list_regions(regions_dir):
        try:
            cfg = load_region(stem, regions_dir=regions_dir)
        except ConfigError as exc:
            errors.append(str(exc))
            continue
        prefixes.setdefault(cfg.id_prefix, []).append(Path(regions_dir) / f"{stem}.yaml")
    for prefix, files in sorted(prefixes.items()):
        if len(files) > 1:
            names = " and ".join(str(f) for f in files)
            errors.append(f"id_prefix {prefix!r} is used by more than one region: {names}")
    return errors


def _placement_config(placement: Mapping[str, Any]) -> PlacementConfig:
    clamp = placement.get("scale_clamp")
    return PlacementConfig(scale_clamp=None if clamp is None else float(clamp))
