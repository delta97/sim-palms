"""Typed palmscan configuration.

The region file is loaded and validated by :mod:`palmcore.config` (``RegionConfig``: bbox,
``id_prefix``, inventory sources, masks, priors, the ``exclusion:`` clamps). This module adds
the ``palmscan:`` block as frozen dataclasses whose defaults are the plan's thresholds, so
code never reads raw dicts. Unknown keys raise :class:`palmcore.errors.ConfigError`.
"""

from __future__ import annotations

import dataclasses
import difflib
import hashlib
import types
import typing
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Union

from palmcore.cache import canonical_json
from palmcore.config import InventorySource as InventorySourceCfg
from palmcore.config import MaskArea, RegionConfig, load_region, load_region_dict
from palmcore.errors import ConfigError
from palmcore.geo import Bbox

__all__ = [
    "ClassifyParams",
    "ExclusionParams",
    "InventoryParams",
    "InventorySourceCfg",
    "LidarParams",
    "MaskArea",
    "MergeParams",
    "PalmFilterParams",
    "PeakParams",
    "QaParams",
    "RuleParams",
    "ScanConfig",
    "load_scan_config",
    "scan_config_from_mapping",
    "scan_config_from_region",
]

MAX_BBOX_SPAN_DEG = 1.0


@dataclass(frozen=True)
class PalmFilterParams:
    genus_sets: tuple[str, ...] = ("socal",)  # keys of palm_genera.yaml: socal, florida
    exclude_species: tuple[str, ...] = ()  # e.g. phoenix_roebelenii for shrub palms


@dataclass(frozen=True)
class InventoryParams:
    height_min_m: float = 3.0  # parsed inventory heights outside this range are ignored
    height_max_m: float = 40.0


@dataclass(frozen=True)
class ExclusionParams:
    # radius_min_m / radius_max_m / margin_m are region ``exclusion:`` keys (RegionConfig).
    building_overlap_min_m2: float = 0.1


@dataclass(frozen=True)
class LidarParams:  # Phase 4
    datasets: tuple[str, ...] = ()  # force EPT dataset names; empty = auto-select
    tile_size_m: float = 500.0
    tile_buffer_m: float = 20.0
    resolution_m: float = 0.5
    smooth_sigma_px: float = 1.0
    noise_classes: tuple[int, ...] = (7, 18)
    use_building_class: bool = True


@dataclass(frozen=True)
class PeakParams:
    min_height_m: float = 6.0
    min_distance_m: float = 3.0
    crown_mask_height_m: float = 2.0


@dataclass(frozen=True)
class RuleParams:
    height_min_m: float = 8.0
    height_max_m: float = 35.0
    crown_min_m: float = 3.0
    crown_max_m: float = 12.0
    ratio_min: float = 2.0
    ratio_exempt_large_crown: bool = True
    ratio_exempt_crown_min_m: float = 7.0
    ratio_exempt_ratio_min: float = 1.0
    shared_boundary_max: float = 0.35
    building_buffer_m: float = 1.0


@dataclass(frozen=True)
class MergeParams:
    match_radius_m: float = 3.0
    region_median_min_n: int = 5


@dataclass(frozen=True)
class ClassifyParams:
    use_tree: bool = True
    tree_max_depth: int = 4
    tree_min_samples_leaf: int = 5
    tree_min_class_n: int = 15
    tree_min_total_n: int = 50
    tree_min_gain: float = 0.05
    tree_model_path: str | None = None  # reuse a species_tree.json from another region


@dataclass(frozen=True)
class QaParams:
    vintage_grid_deg: float = 0.01  # matches the palmgen tile size
    stale_years: int = 5
    write_crowns: bool = False
    list_non_palms: bool = False


# ---------------------------------------------------------------------------------------------
# Mapping -> dataclass


def _dotted(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _type_name(value: Any) -> str:
    return type(value).__name__


def _coerce(hint: Any, value: Any, where: str) -> Any:
    """Check ``value`` against a field type hint and normalise lists to tuples."""
    origin = typing.get_origin(hint)
    if origin in (Union, types.UnionType):
        options = typing.get_args(hint)
        if value is None and type(None) in options:
            return None
        inner = [o for o in options if o is not type(None)]
        return _coerce(inner[0], value, where)
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise ConfigError(f"palmscan config: {where} must be a list, got {_type_name(value)}")
        item_hint = typing.get_args(hint)[0]
        return tuple(_coerce(item_hint, v, f"{where}[{i}]") for i, v in enumerate(value))
    if hint is bool:
        if not isinstance(value, bool):
            raise ConfigError(f"palmscan config: {where} must be true or false, got {value!r}")
        return value
    if hint is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"palmscan config: {where} must be an integer, got {value!r}")
        return value
    if hint is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(f"palmscan config: {where} must be a number, got {value!r}")
        return float(value)
    if hint is str:
        if not isinstance(value, str):
            raise ConfigError(f"palmscan config: {where} must be a string, got {value!r}")
        return value
    raise TypeError(f"unsupported config field type {hint!r} at {where}")  # pragma: no cover


def _unknown_key_message(cls: type, path: str, key: str, known: list[str]) -> str:
    where = _dotted(path, key)
    msg = f"palmscan config: unknown key {where!r}"
    close = difflib.get_close_matches(key, known, n=1)
    if close:
        msg += f" (did you mean {close[0]!r}?)"
    elif key == "id_prefix":
        msg += ": id_prefix is a top-level region key, not part of the palmscan: block"
    elif cls is ExclusionParams and key in ("margin_m", "radius_min_m", "radius_max_m"):
        msg += f": {key} belongs to the region's top-level exclusion: block"
    else:
        msg += f"; known keys: {', '.join(sorted(known))}"
    return msg


def _build_block(cls: type, raw: Any, path: str, *, skip: tuple[str, ...] = ()) -> dict[str, Any]:
    """Validate ``raw`` against dataclass ``cls`` and return constructor kwargs."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ConfigError(f"palmscan config: {path or 'palmscan'} must be a mapping")
    hints = typing.get_type_hints(cls)
    known = [f.name for f in dataclasses.fields(cls) if f.name not in skip]
    kwargs: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in known:
            raise ConfigError(_unknown_key_message(cls, path, str(key), known))
        hint = hints[key]
        where = _dotted(path, key)
        if isinstance(hint, type) and dataclasses.is_dataclass(hint):
            kwargs[key] = hint(**_build_block(hint, value, where))
        else:
            kwargs[key] = _coerce(hint, value, where)
    return kwargs


def _check_order(low: float, high: float, low_name: str, high_name: str) -> None:
    if low >= high:
        raise ConfigError(
            f"palmscan config: {low_name} ({low}) must be less than {high_name} ({high})"
        )


@dataclass(frozen=True)
class ScanConfig:
    """Everything palmscan needs: the validated region plus the ``palmscan:`` blocks."""

    region: RegionConfig
    output_dir: str | None = None  # default build/scan/<region>
    allow_large_bbox: bool = False
    dedupe_radius_m: float = 2.0
    palm_filter: PalmFilterParams = field(default_factory=PalmFilterParams)
    inventory: InventoryParams = field(default_factory=InventoryParams)
    exclusion: ExclusionParams = field(default_factory=ExclusionParams)
    lidar: LidarParams = field(default_factory=LidarParams)
    peaks: PeakParams = field(default_factory=PeakParams)
    rules: RuleParams = field(default_factory=RuleParams)
    merge: MergeParams = field(default_factory=MergeParams)
    classify: ClassifyParams = field(default_factory=ClassifyParams)
    qa: QaParams = field(default_factory=QaParams)

    # Region-level values, read from RegionConfig rather than duplicated.
    @property
    def region_name(self) -> str:
        return self.region.region

    @property
    def id_prefix(self) -> str:
        return self.region.id_prefix

    @property
    def bbox(self) -> Bbox:
        return self.region.bbox

    @property
    def mask_out(self) -> tuple[MaskArea, ...]:
        return self.region.mask_out

    @property
    def species_priors(self) -> Mapping[str, float]:
        return self.region.species_priors

    def scan_params(self) -> dict[str, Any]:
        """The resolved ``palmscan:`` blocks as a plain, JSON-able dict."""
        out: dict[str, Any] = {}
        for f in dataclasses.fields(self):
            if f.name == "region":
                continue
            value = getattr(self, f.name)
            is_block = dataclasses.is_dataclass(value) and not isinstance(value, type)
            out[f.name] = dataclasses.asdict(value) if is_block else value
        return out

    def config_hash(self) -> str:
        """sha256 of the canonical JSON of the fully resolved config (region + palmscan)."""
        payload = {"region": self.region.to_dict(), "palmscan": self.scan_params()}
        return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def scan_config_from_region(region: RegionConfig) -> ScanConfig:
    """Build a :class:`ScanConfig` from a loaded region, validating its ``palmscan:`` block."""
    kwargs = _build_block(ScanConfig, region.palmscan, "", skip=("region",))
    cfg = ScanConfig(region=region, **kwargs)
    _validate(cfg)
    return cfg


def _validate(cfg: ScanConfig) -> None:
    bbox = cfg.region.bbox
    span_lon = bbox.lon_max - bbox.lon_min
    span_lat = bbox.lat_max - bbox.lat_min
    if not cfg.allow_large_bbox and (span_lon > MAX_BBOX_SPAN_DEG or span_lat > MAX_BBOX_SPAN_DEG):
        raise ConfigError(
            f"palmscan config: bbox spans {span_lon:.3f} x {span_lat:.3f} deg, more than "
            f"{MAX_BBOX_SPAN_DEG} deg in one axis; fix a typo or set "
            "palmscan.allow_large_bbox: true"
        )
    _check_order(
        cfg.inventory.height_min_m,
        cfg.inventory.height_max_m,
        "inventory.height_min_m",
        "inventory.height_max_m",
    )
    _check_order(
        cfg.rules.height_min_m, cfg.rules.height_max_m, "rules.height_min_m", "rules.height_max_m"
    )
    _check_order(
        cfg.rules.crown_min_m, cfg.rules.crown_max_m, "rules.crown_min_m", "rules.crown_max_m"
    )
    for name, value in (
        ("dedupe_radius_m", cfg.dedupe_radius_m),
        ("lidar.resolution_m", cfg.lidar.resolution_m),
        ("lidar.tile_size_m", cfg.lidar.tile_size_m),
        ("merge.match_radius_m", cfg.merge.match_radius_m),
    ):
        if value <= 0:
            raise ConfigError(f"palmscan config: {name} must be greater than 0, got {value}")


def scan_config_from_mapping(raw: Mapping[str, Any], base_dir: Path | None = None) -> ScanConfig:
    """Build a config from an in-memory region mapping (no file); used by tests.

    ``config_version`` defaults to 1 so a mapping with only ``region`` and ``bbox`` works.
    """
    data = {"config_version": 1, **raw}
    region = load_region_dict(data, base_dir=Path.cwd() if base_dir is None else Path(base_dir))
    return scan_config_from_region(region)


def load_scan_config(region: str | Path, regions_dir: Path = Path("regions")) -> ScanConfig:
    """Load ``regions_dir/<region>.yaml`` (or a ``.yaml`` path) as a :class:`ScanConfig`."""
    return scan_config_from_region(load_region(region, regions_dir=Path(regions_dir)))
