from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import pytest
import yaml

from palmcore.config import ExclusionConfig
from palmgen.errors import InputError
from palmgen.geometry import RADIUS_CLAMPED, RADIUS_DEFAULTED, RadiusConfig, palm_radius
from palmgen.inputs import GenConfig, load_buildings, load_gen_config, load_palms
from palmgen.model import Palm
from tests.helpers.fixtures import FIXTURES_ROOT

FIX = FIXTURES_ROOT / "palmgen"
PALMS = FIX / "palms_small.geojson"
BUILDINGS = FIX / "buildings_small.geojson"
REGION_YAML = FIX / "region_small.yaml"
REGION = "fixture-small"


def _doc(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _write(tmp_path: Path, name: str, doc: Any) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _region_file(tmp_path: Path, **overrides: Any) -> Path:
    data = yaml.safe_load(REGION_YAML.read_text(encoding="utf-8"))
    data.update(overrides)
    path = tmp_path / "regions" / "x.yaml"
    path.parent.mkdir(exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


# --- load_palms ----------------------------------------------------------------------------------


def test_load_palms_fixture() -> None:
    palms, _ = load_palms(PALMS, REGION)
    assert len(palms) == 12
    assert [p.palm_id for p in palms] == sorted(p.palm_id for p in palms)
    assert all(isinstance(p, Palm) for p in palms)
    first = palms[0]
    assert (first.palm_id, first.species) == ("fs-0000000000000001", "washingtonia_robusta")
    assert first.exclusion_radius_m == 2.0
    assert first.building_conflict is False
    assert palms[7].building_conflict is True  # palm 8 touches a building
    assert palms[8].building_conflict is True  # palm 9 is inside one


def test_load_palms_metadata_is_every_member_but_type_and_features() -> None:
    _, meta = load_palms(PALMS, REGION)
    assert set(meta) == {
        "schema_version",
        "region",
        "generated_at",
        "data_version",
        "generator",
        "config_sha256",
    }
    assert meta["data_version"] == "2026-11"
    assert meta["generator"] == {"name": "palmscan", "version": "0.1.0"}


def test_load_palms_keeps_foreign_members(tmp_path: Path) -> None:
    doc = _doc(PALMS)
    doc["bbox"] = [-117.265, 32.775, -117.235, 32.795]
    doc["x_note"] = "hello"
    _, meta = load_palms(_write(tmp_path, "p.geojson", doc), REGION)
    assert meta["bbox"] == [-117.265, 32.775, -117.235, 32.795]
    assert meta["x_note"] == "hello"


def test_load_palms_sorts_shuffled_input(tmp_path: Path) -> None:
    doc = _doc(PALMS)
    doc["features"].reverse()
    palms, _ = load_palms(_write(tmp_path, "p.geojson", doc), REGION)
    assert [p.palm_id for p in palms] == sorted(p.palm_id for p in palms)


def test_load_palms_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="palms file not found"):
        load_palms(tmp_path / "nope.geojson", REGION)


def test_load_palms_not_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.geojson"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(InputError, match="cannot read"):
        load_palms(path, REGION)


def test_load_palms_not_an_object(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="must be an object"):
        load_palms(_write(tmp_path, "p.geojson", [1, 2]), REGION)


def test_load_palms_schema_failure_lists_first_20_errors(tmp_path: Path) -> None:
    doc = _doc(PALMS)
    doc["features"] = [
        {**f, "properties": {**f["properties"], "height_m": -1}} for f in doc["features"]
    ] * 1
    doc["features"] += [
        {**f, "properties": {**f["properties"], "palm_id": f"fs-{i:016d}", "height_m": -1}}
        for i, f in enumerate(doc["features"] * 3, start=100)
    ]
    path = _write(tmp_path, "p.geojson", doc)
    with pytest.raises(InputError) as info:
        load_palms(path, REGION)
    message = str(info.value)
    assert "invalid palms.geojson" in message
    listed = [line for line in message.splitlines() if line.startswith("  ")]
    assert len(listed) == 20


def test_load_palms_duplicate_palm_id(tmp_path: Path) -> None:
    doc = _doc(PALMS)
    doc["features"].append(doc["features"][0])
    with pytest.raises(InputError, match="duplicate palm_id"):
        load_palms(_write(tmp_path, "p.geojson", doc), REGION)


def test_load_palms_file_region_differs(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="does not match expected"):
        load_palms(PALMS, "other-region")


def test_load_palms_feature_region_differs(tmp_path: Path) -> None:
    doc = _doc(PALMS)
    doc["features"][3]["properties"]["region"] = "other-region"
    with pytest.raises(InputError, match="does not match file region"):
        load_palms(_write(tmp_path, "p.geojson", doc), REGION)


# --- load_buildings ------------------------------------------------------------------------------


def _bfeature(building_id: str, geometry: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {"building_id": building_id, "source": "test"},
    }


def _bdoc(*features: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "schema_version": "1.0",
        "region": REGION,
        "features": list(features),
    }


def _square(x: float, y: float, size: float = 0.001) -> list[list[list[float]]]:
    return [[[x, y], [x + size, y], [x + size, y + size], [x, y + size], [x, y]]]


def test_load_buildings_fixture() -> None:
    polys = load_buildings(BUILDINGS)
    assert len(polys) == 2
    assert all(p.is_valid and not p.is_empty for p in polys)
    # fixture:containing contains palm 9, fixture:touching reaches palm 8.
    palms = {p.palm_id: p for p in load_palms(PALMS, REGION)[0]}
    from shapely.geometry import Point

    nine = palms["fs-0000000000000009"]
    assert any(poly.contains(Point(nine.lon, nine.lat)) for poly in polys)


def test_load_buildings_missing_file_hint(tmp_path: Path) -> None:
    with pytest.raises(InputError, match=r"--buildings.*clip_buildings: false"):
        load_buildings(tmp_path / "buildings.geojson")


def test_load_buildings_not_json(tmp_path: Path) -> None:
    path = tmp_path / "b.geojson"
    path.write_text("nope", encoding="utf-8")
    with pytest.raises(InputError, match="cannot read"):
        load_buildings(path)


def test_load_buildings_not_an_object(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="must be an object"):
        load_buildings(_write(tmp_path, "b.geojson", []))


def test_load_buildings_schema_failure(tmp_path: Path) -> None:
    doc = _bdoc(_bfeature("a", {"type": "Point", "coordinates": [0, 0]}))
    with pytest.raises(InputError, match=r"invalid buildings.geojson"):
        load_buildings(_write(tmp_path, "b.geojson", doc))


def test_load_buildings_duplicate_id(tmp_path: Path) -> None:
    geom = {"type": "Polygon", "coordinates": _square(-117.0, 32.0)}
    doc = _bdoc(_bfeature("a", geom), _bfeature("a", geom))
    with pytest.raises(InputError, match="duplicate building_id"):
        load_buildings(_write(tmp_path, "b.geojson", doc))


def test_load_buildings_error_list_is_capped(tmp_path: Path) -> None:
    point = {"type": "Point", "coordinates": [0, 0]}
    doc = _bdoc(*(_bfeature(f"b{i}", point) for i in range(30)))
    with pytest.raises(InputError) as info:
        load_buildings(_write(tmp_path, "b.geojson", doc))
    listed = [line for line in str(info.value).splitlines() if line.startswith("  ")]
    assert len(listed) == 21  # 20 errors plus the "..." marker


def test_load_buildings_explodes_multipolygon(tmp_path: Path) -> None:
    multi = {
        "type": "MultiPolygon",
        "coordinates": [_square(-117.0, 32.0), _square(-116.9, 32.0)],
    }
    polys = load_buildings(_write(tmp_path, "b.geojson", _bdoc(_bfeature("m", multi))))
    assert len(polys) == 2
    assert all(p.geom_type == "Polygon" for p in polys)


def test_load_buildings_repairs_invalid_geometry(tmp_path: Path) -> None:
    bowtie = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [0.001, 0.001], [0.001, 0], [0, 0.001], [0, 0]]],
    }
    polys = load_buildings(_write(tmp_path, "b.geojson", _bdoc(_bfeature("bow", bowtie))))
    assert len(polys) == 2  # make_valid splits the bowtie into two triangles
    assert all(p.is_valid for p in polys)


def test_load_buildings_drops_empty_results(tmp_path: Path) -> None:
    flat = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [2, 2], [0, 0]]]}
    good = {"type": "Polygon", "coordinates": _square(-117.0, 32.0)}
    doc = _bdoc(_bfeature("a-flat", flat), _bfeature("b-good", good))
    polys = load_buildings(_write(tmp_path, "b.geojson", doc))
    assert len(polys) == 1


def test_load_buildings_bad_ring(tmp_path: Path) -> None:
    short = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0]]]}
    with pytest.raises(InputError, match="bad geometry"):
        load_buildings(_write(tmp_path, "b.geojson", _bdoc(_bfeature("short", short))))


def test_load_buildings_order_follows_building_id(tmp_path: Path) -> None:
    west = {"type": "Polygon", "coordinates": _square(-117.0, 32.0)}
    east = {"type": "Polygon", "coordinates": _square(-116.0, 32.0)}
    doc = _bdoc(_bfeature("b", east), _bfeature("a", west))
    polys = load_buildings(_write(tmp_path, "b.geojson", doc))
    assert polys[0].bounds[0] == -117.0


# --- load_gen_config -----------------------------------------------------------------------------


def test_gen_config_fixture() -> None:
    cfg = load_gen_config(REGION, REGION_YAML)
    assert cfg.region == REGION
    assert cfg.id_prefix == "fs"
    assert (cfg.bbox.lon_min, cfg.bbox.lat_max) == (-117.265, 32.795)
    assert [(m.name, m.kind) for m in cfg.mask_out] == [("fixture-mod", "mod")]
    assert cfg.airports.enabled is True
    assert cfg.species_priors["washingtonia_robusta"] == pytest.approx(0.6)
    assert cfg.config_sha256 == hashlib.sha256(REGION_YAML.read_bytes()).hexdigest()


def test_gen_config_is_frozen() -> None:
    cfg = load_gen_config(REGION, REGION_YAML)
    with pytest.raises(AttributeError):
        cfg.region = "other"  # type: ignore[misc]


def test_gen_config_defaults_match_plan_table() -> None:
    cfg = load_gen_config(REGION, REGION_YAML)
    ex = cfg.exclusion
    assert (ex.margin_m, ex.polygon_sides, ex.merge_gap_m, ex.clip_buildings) == (
        1.5,
        12,
        2.0,
        True,
    )
    assert (ex.clip_buffer_m, ex.min_part_area_m2) == (0.3, 1.0)
    assert (ex.radius_min_m, ex.radius_max_m, ex.default_radius_m) == (1.0, 8.0, 3.0)
    assert (ex.max_cluster_extent_m, ex.max_vertices) == (150.0, 256)
    assert (cfg.airports.enabled, cfg.airports.buffer_m) == (True, 100.0)
    assert cfg.airports.path is not None
    assert cfg.airports.path.is_absolute()
    assert cfg.airports.path.as_posix().endswith("docs/compat/airports-mask.geojson")
    assert ex == ExclusionConfig()  # nothing is redefined on the palmgen side


def test_gen_config_scale_clamp_is_none_unless_set(tmp_path: Path) -> None:
    assert load_gen_config(REGION, REGION_YAML).scale_clamp is None
    path = _region_file(tmp_path, placement={"scale_clamp": 0.2})
    assert load_gen_config(REGION, path).scale_clamp == 0.2


def test_gen_config_relative_paths_resolve_against_base_dir(tmp_path: Path) -> None:
    path = _region_file(tmp_path, masks={"airports": {"path": "data/air.geojson"}})
    cfg = load_gen_config(REGION, path)
    assert cfg.airports.path == (tmp_path / "data" / "air.geojson").resolve()
    other = tmp_path / "elsewhere"
    cfg = load_gen_config(REGION, path, base_dir=other)
    assert cfg.airports.path == (other.resolve() / "data" / "air.geojson")


def test_gen_config_unknown_exclusion_key_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = _region_file(tmp_path, exclusion={"margin_m": 2.5, "bogus_key": 1})
    with caplog.at_level(logging.WARNING, logger="palmfix"):
        cfg = load_gen_config(REGION, path)
    assert cfg.margin_m == 2.5
    assert any("bogus_key" in r.getMessage() for r in caplog.records)


def test_gen_config_region_mismatch(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="requested region is 'other-region'"):
        load_gen_config("other-region", REGION_YAML)


def test_gen_config_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InputError, match="cannot read region config"):
        load_gen_config(REGION, tmp_path / "missing.yaml")


def test_gen_config_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("region: [unclosed", encoding="utf-8")
    with pytest.raises(InputError, match="invalid YAML"):
        load_gen_config(REGION, path)


def test_gen_config_schema_error(tmp_path: Path) -> None:
    path = _region_file(tmp_path, exclusion={"margin_m": -4})
    with pytest.raises(InputError, match=r"exclusion\.margin_m"):
        load_gen_config(REGION, path)


# --- RadiusConfig --------------------------------------------------------------------------------


def test_gen_config_satisfies_radius_config() -> None:
    cfg = load_gen_config(REGION, REGION_YAML)
    as_protocol: RadiusConfig = cfg  # mypy checks the structural match
    assert (as_protocol.margin_m, as_protocol.radius_min_m) == (1.5, 1.0)
    assert (as_protocol.default_radius_m, as_protocol.radius_max_m) == (3.0, 8.0)


def _palm(**kw: Any) -> Palm:
    base: dict[str, Any] = {
        "palm_id": "fs-0000000000000001",
        "lon": -117.255,
        "lat": 32.785,
        "species": "washingtonia_robusta",
        "height_m": 10.0,
        "crown_diam_m": None,
        "exclusion_radius_m": None,
        "building_conflict": False,
    }
    base.update(kw)
    return Palm(**base)


def test_palm_radius_reads_gen_config() -> None:
    cfg = load_gen_config(REGION, REGION_YAML)
    assert palm_radius(_palm(crown_diam_m=4.0), cfg, None) == (3.5, None)  # 4/2 + margin 1.5
    assert palm_radius(_palm(), cfg, None) == (3.0, RADIUS_DEFAULTED)
    assert palm_radius(_palm(exclusion_radius_m=0.3), cfg, None) == (1.0, RADIUS_CLAMPED)
    assert palm_radius(_palm(crown_diam_m=4.0), cfg, 0.5) == (2.5, None)


def test_fixture_palms_run_through_palm_radius() -> None:
    cfg = load_gen_config(REGION, REGION_YAML)
    palms, _ = load_palms(PALMS, REGION)
    by_id = {p.palm_id: p for p in palms}
    assert palm_radius(by_id["fs-0000000000000012"], cfg, None) == (1.0, RADIUS_CLAMPED)
    assert palm_radius(by_id["fs-0000000000000001"], cfg, None) == (2.0, None)


def test_from_region_maps_without_defaults() -> None:
    cfg = load_gen_config(REGION, REGION_YAML)
    assert isinstance(cfg, GenConfig)
    assert cfg.exclusion.radius_max_m == cfg.radius_max_m
