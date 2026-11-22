"""Tests for palmcore.config (region YAML loader) and schemas/region.schema.json."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import pytest

from palmcore import config
from palmcore.config import (
    AirportMasks,
    ExclusionConfig,
    PlacementConfig,
    RegionConfig,
    check_regions,
    list_regions,
    load_region,
    load_region_dict,
)
from palmcore.errors import ConfigError
from palmcore.schemas import load_schema

REGIONS = Path(__file__).resolve().parents[2] / "fixtures" / "palmcore" / "regions"
BASE = REGIONS.parent
INVALID = REGIONS / "invalid"
EXPECTED: dict[str, str] = json.loads((INVALID / "expected.json").read_text(encoding="utf-8"))


def _comparable(cfg: RegionConfig) -> RegionConfig:
    return dataclasses.replace(cfg, source_path=None, sha256="", raw={})


def _load(name: str) -> RegionConfig:
    return load_region(REGIONS / f"{name}.yaml")


def test_minimal_defaults() -> None:
    cfg = _load("minimal")
    assert cfg.region == "minimal"
    assert cfg.id_prefix == "min"
    assert cfg.name == "minimal"
    assert cfg.local_crs is None
    assert cfg.crs() == "EPSG:32611"
    assert cfg.exclusion == ExclusionConfig()
    assert cfg.placement == PlacementConfig()
    assert cfg.sources.inventory == ()
    assert (cfg.sources.lidar.type, dict(cfg.sources.lidar.options)) == ("none", {})
    assert cfg.sources.buildings.type == "none"
    assert cfg.sources.buildings_path is None
    assert cfg.sources.overpass_url == config.DEFAULT_OVERPASS_URL
    assert cfg.sources.osm_trees is False
    assert dict(cfg.species_priors) == {}
    assert cfg.mask_out == ()
    assert cfg.palmscan == {}
    assert cfg.palmgen == {}
    assert cfg.airport_masks.enabled is True
    assert cfg.airport_masks.buffer_m == 100.0


def test_id_prefix_initials() -> None:
    data = {
        "config_version": 1,
        "region": "san-diego-coastal",
        "bbox": [-117.3, 32.6, -117.0, 32.9],
    }
    assert load_region_dict(data, base_dir=BASE).id_prefix == "sdc"


def test_airport_path_default_is_absolute() -> None:
    cfg = _load("minimal")
    assert cfg.airport_masks.path == (BASE / "docs/compat/airports-mask.geojson").resolve()
    assert cfg.airport_masks.path is not None
    assert cfg.airport_masks.path.is_absolute()
    assert AirportMasks().path is None  # only the loader fills it


def test_full_values_and_absolute_paths() -> None:
    cfg = _load("full")
    base = BASE.resolve()
    assert cfg.id_prefix == "fll"
    assert cfg.local_crs == "EPSG:26911"
    assert cfg.crs() == "EPSG:26911"
    arc, geo = cfg.sources.inventory
    assert arc.url is not None
    assert arc.path is None
    assert arc.format is None
    assert arc.where == "STATUS = 'Active'"
    assert arc.height_units == "m"
    assert arc.cache_max_age_days == 30.0
    assert arc.options == {"page_size": 1000}
    assert geo.path == base / "data/inventory/park_trees.csv"
    assert geo.format == "csv"
    assert geo.where is None
    assert geo.vintage == "2022-01-15"  # stays text, not a date
    assert cfg.sources.lidar.type == "3dep_ept"
    assert dict(cfg.sources.lidar.options) == {"resolution_m": 0.5}
    assert cfg.sources.buildings.type == "microsoft_footprints"
    assert cfg.sources.buildings_path == base / "data/buildings/local.geojson"
    assert cfg.exclusion.max_vertices == 128
    assert cfg.exclusion.clip_buildings is False
    assert cfg.placement.scale_clamp == 0.2
    mod, airport, from_file = cfg.mask_out
    assert (mod.kind, airport.kind, from_file.kind) == ("mod", "airport", "other")
    assert mod.bbox is not None
    assert airport.geometry is not None
    assert from_file.path == base / "data/masks/extra.geojson"
    assert cfg.airport_masks == AirportMasks(
        enabled=False, buffer_m=150.0, path=base / "docs/compat/airports-mask.geojson"
    )
    assert cfg.palmscan["dedupe_radius_m"] == 2.0
    assert cfg.palmgen["note"] == "free form"


def test_full_round_trip() -> None:
    cfg = _load("full")
    again = load_region_dict(cfg.to_dict(), base_dir=BASE)
    assert _comparable(again) == _comparable(cfg)


def test_raw_and_sha256() -> None:
    path = REGIONS / "minimal.yaml"
    cfg = load_region(path)
    assert cfg.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert cfg.raw["region"] == "minimal"
    assert "id_prefix" not in cfg.raw  # raw is before defaults
    assert cfg.source_path == path


def test_frozen() -> None:
    cfg = _load("full")
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.region = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.exclusion.margin_m = 9.0  # type: ignore[misc]
    with pytest.raises(TypeError):
        cfg.raw["region"] = "x"  # type: ignore[index]
    with pytest.raises(TypeError):
        cfg.species_priors["a_b"] = 1.0  # type: ignore[index]


@pytest.mark.parametrize("case", sorted(EXPECTED))
def test_invalid_cases(case: str) -> None:
    with pytest.raises(ConfigError) as info:
        load_region(INVALID / case)
    message = str(info.value)
    assert EXPECTED[case] in message
    assert case in message  # names the file


def test_invalid_expected_covers_every_file() -> None:
    assert {p.name for p in INVALID.glob("*.yaml")} == set(EXPECTED)


def test_unknown_key_names_dotted_path() -> None:
    with pytest.raises(ConfigError) as info:
        load_region(INVALID / "unknown_key.yaml")
    assert "unknown_key.yaml: exclusion.marginm: unknown key 'marginm'" in str(info.value)


def test_two_errors_reported_together() -> None:
    data: dict[str, Any] = {
        "config_version": 1,
        "region": "two-errors",
        "bbox": [-117.3, 32.6, -117.0, 32.9],
        "exclusion": {"margin_m": 99, "bogus": 1},
    }
    with pytest.raises(ConfigError) as info:
        load_region_dict(data, base_dir=BASE)
    message = str(info.value)
    assert "exclusion.margin_m" in message
    assert "exclusion.bogus: unknown key 'bogus'" in message
    assert len(message.splitlines()) == 2


def test_semantic_errors_reported_together() -> None:
    data: dict[str, Any] = {
        "config_version": 1,
        "region": "semantic",
        "bbox": [-117.3, 32.6, -117.0, 32.9],
        "local_crs": "not-a-crs",
        "species_priors": {"a_b": 0},
        "mask_out": [
            {"name": "m", "bbox": [0, 0, 1, 1]},
            {"name": "m", "bbox": [2, 2, 1, 1]},
        ],
    }
    with pytest.raises(ConfigError) as info:
        load_region_dict(data, base_dir=BASE)
    message = str(info.value)
    for needle in ("local_crs", "species_priors", "duplicate mask name", "mask_out[1].bbox"):
        assert needle in message


def test_priors_normalise() -> None:
    data = {
        "config_version": 1,
        "region": "pri",
        "bbox": [-117.3, 32.6, -117.0, 32.9],
        "species_priors": {"a_b": 2, "c_d": 2},
    }
    cfg = load_region_dict(data, base_dir=BASE)
    assert dict(cfg.species_priors) == {"a_b": 0.5, "c_d": 0.5}


def test_relative_paths_resolve_under_base_dir(tmp_path: Path) -> None:
    data = {
        "config_version": 1,
        "region": "rel",
        "bbox": [-117.3, 32.6, -117.0, 32.9],
        "sources": {
            "buildings_path": "data/b.geojson",
            "inventory": [
                {
                    "name": "t",
                    "type": "geojson_file",
                    "path": "data/t.geojson",
                    "species_field": "s",
                }
            ],
        },
        "mask_out": [{"name": "m", "path": "masks/m.geojson"}],
    }
    cfg = load_region_dict(data, base_dir=tmp_path)
    root = tmp_path.resolve()
    assert cfg.sources.buildings_path == root / "data" / "b.geojson"
    assert cfg.sources.inventory[0].path == root / "data" / "t.geojson"
    assert cfg.sources.inventory[0].format == "geojson"
    assert cfg.mask_out[0].path == root / "masks" / "m.geojson"
    assert cfg.airport_masks.path == root / "docs" / "compat" / "airports-mask.geojson"


def test_check_regions_reports_shared_prefix() -> None:
    errors = check_regions(REGIONS / "dup_prefix")
    assert len(errors) == 1
    assert "alpha-one.yaml" in errors[0]
    assert "beta-two.yaml" in errors[0]
    assert "'shr'" in errors[0]


def test_check_regions_reports_bad_file(tmp_path: Path) -> None:
    (tmp_path / "ok.yaml").write_text(
        "config_version: 1\nregion: ok\nbbox: [0, 0, 1, 1]\n", encoding="utf-8"
    )
    (tmp_path / "bad.yaml").write_text("config_version: 1\nregion: bad\n", encoding="utf-8")
    errors = check_regions(tmp_path)
    assert len(errors) == 1
    assert "bad.yaml: bbox: 'bbox' is a required property" in errors[0]


def test_list_regions_skips_underscore_and_non_yaml() -> None:
    assert list_regions(REGIONS / "dup_prefix") == ["alpha-one", "beta-two"]
    assert list_regions(REGIONS) == ["full", "minimal"]


def test_load_by_slug_and_base_dir() -> None:
    cfg = load_region("minimal", regions_dir=REGIONS)
    assert cfg.region == "minimal"
    assert cfg.airport_masks.path is not None
    assert cfg.airport_masks.path.parent.parent.parent == BASE.resolve()


def test_slug_needs_regions_dir() -> None:
    with pytest.raises(ConfigError, match="regions_dir is required"):
        load_region("minimal")


@pytest.mark.parametrize("slug", ["../minimal", "..", "a/b", "a\\b", "Bad_Name", ""])
def test_bad_slug_rejected_before_file_access(
    slug: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: Path) -> bytes:
        raise AssertionError("file was accessed")

    monkeypatch.setattr(Path, "read_bytes", boom)
    with pytest.raises(ConfigError, match="invalid region name"):
        load_region(slug, regions_dir=tmp_path)


def test_empty_and_non_mapping_files(tmp_path: Path) -> None:
    empty = tmp_path / "empty.yaml"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ConfigError, match="file is empty"):
        load_region(empty)
    listing = tmp_path / "listing.yaml"
    listing.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="top level must be a mapping"):
        load_region(listing)
    broken = tmp_path / "broken.yaml"
    broken.write_text("a: [1, 2\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="invalid YAML"):
        load_region(broken)


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read region file"):
        load_region(tmp_path / "nope.yaml")


def test_mask_outside_region_warns(caplog: pytest.LogCaptureFixture) -> None:
    data = {
        "config_version": 1,
        "region": "warn",
        "bbox": [-117.3, 32.6, -117.0, 32.9],
        "mask_out": [{"name": "far", "bbox": [10, 10, 11, 11]}],
    }
    with caplog.at_level(logging.WARNING, logger="palmcore.config"):
        load_region_dict(data, base_dir=BASE)
    assert "far" in caplog.text


def test_schema_defaults_match_python_defaults() -> None:
    props = load_schema("region")["properties"]
    for name, field in ExclusionConfig.__dataclass_fields__.items():
        default = getattr(ExclusionConfig(), name)
        assert props["exclusion"]["properties"][name]["default"] == default, name
        assert isinstance(default, type(field.default)), name
    # scale_clamp is an optional override with no default (ASSET-005 owns scale limits).
    assert "default" not in props["placement"]["properties"]["scale_clamp"]
    assert PlacementConfig().scale_clamp is None
    airports = props["masks"]["properties"]["airports"]["properties"]
    assert airports["enabled"]["default"] == AirportMasks().enabled
    assert airports["buffer_m"]["default"] == AirportMasks().buffer_m
    assert airports["path"]["default"] == config.DEFAULT_AIRPORT_MASK_PATH
    sources = props["sources"]["properties"]
    assert sources["overpass_url"]["default"] == config.DEFAULT_OVERPASS_URL
    assert sources["lidar"]["default"] == config.DEFAULT_LIDAR
    assert sources["buildings"]["default"] == config.DEFAULT_BUILDINGS
    assert sources["osm_trees"]["default"] is False
    assert sources["inventory"]["default"] == []
    assert sources["buildings_path"]["default"] is None
    assert props["local_crs"]["default"] is None
    assert props["species_priors"]["default"] == {}
    assert props["mask_out"]["default"] == []
    assert props["palmscan"]["default"] == {}
    assert props["palmgen"]["default"] == {}
    item = load_schema("region")["$defs"]["inventory_item"]["properties"]
    assert item["height_units"]["default"] == config.DEFAULT_HEIGHT_UNITS
    assert item["where"]["default"] == config.DEFAULT_ARCGIS_WHERE
    mask = load_schema("region")["$defs"]["mask_item"]["properties"]
    assert mask["kind"]["default"] == config.DEFAULT_MASK_KIND


def test_schema_id_and_version() -> None:
    schema = load_schema("region")
    assert schema["$id"] == "urn:palmfix:schema:region:1"
    assert schema["properties"]["config_version"]["const"] in config.SUPPORTED_CONFIG_VERSIONS
