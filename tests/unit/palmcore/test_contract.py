import copy
import json
import re
import time
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from palmcore import contract
from palmcore.contract import (
    check_version,
    parse_version,
    validate_buildings,
    validate_palms,
    validate_palms_file,
)
from palmcore.errors import ContractError, PalmfixError
from palmcore.schemas import load_schema

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "palmcore"
PALMS = FIXTURES / "palms"
BUILDINGS = FIXTURES / "buildings"


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def minimal() -> dict[str, Any]:
    return load(PALMS / "valid_minimal.geojson")


def two_features() -> dict[str, Any]:
    doc = minimal()
    second = copy.deepcopy(doc["features"][0])
    second["id"] = second["properties"]["palm_id"] = "sdc-0000000000000002"
    doc["features"].append(second)
    return doc


def messages(report: contract.ValidationReport) -> str:
    return "\n".join(str(i) for i in report.errors)


def test_schemas_are_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(load_schema("palms"))
    Draft202012Validator.check_schema(
        json.loads(
            (
                Path(contract.__file__).parents[1] / "schemas" / "buildings.geojson.schema.json"
            ).read_text("utf-8")
        )
    )


@pytest.mark.parametrize("path", sorted(PALMS.glob("valid_*.geojson")), ids=lambda p: p.name)
def test_valid_fixtures_pass_read_mode(path: Path) -> None:
    report = validate_palms_file(path)
    assert report.ok, messages(report)


@pytest.mark.parametrize("name", ["valid_minimal", "valid_small"])
def test_valid_fixtures_pass_write_mode(name: str) -> None:
    report = validate_palms_file(PALMS / f"{name}.geojson", mode="write")
    assert report.ok, messages(report)
    assert report.warnings == []


def test_valid_small_counts_and_empty_warns() -> None:
    assert validate_palms_file(PALMS / "valid_small.geojson").feature_count == 10
    empty = validate_palms_file(PALMS / "valid_empty.geojson")
    assert empty.ok
    assert [w.path for w in empty.warnings] == ["features"]  # S9


def test_ground_elev_null_validates() -> None:
    doc = minimal()
    assert doc["features"][0]["properties"]["ground_elev_m"] is None
    assert validate_palms(doc).ok
    description = load_schema("palms")["$defs"]["feature"]["properties"]["properties"][
        "properties"
    ]["ground_elev_m"]["description"]
    assert "orthometric" in description
    assert "VERIFY:" in description
    assert "3DEP" in description


def test_newer_minor_read_warns_once_write_errors() -> None:
    path = PALMS / "newer_minor_1_1.geojson"
    read = validate_palms_file(path)
    assert read.ok, messages(read)
    assert len(read.warnings) == 1
    assert "schema 1.1" in read.warnings[0].message
    write = validate_palms_file(path, mode="write")
    assert not write.ok
    assert len(write.errors) >= 1


INVALID = load(PALMS / "invalid" / "expected.json")


@pytest.mark.parametrize("name", sorted(k for k, v in INVALID.items() if k != "major_2.geojson"))
def test_invalid_cases(name: str) -> None:
    expected = INVALID[name]
    report = validate_palms_file(PALMS / "invalid" / name)
    assert not report.ok
    matches = [
        e for e in report.errors if e.path == expected["path"] and expected["contains"] in e.message
    ]
    assert matches, messages(report)


def test_missing_schema_version_is_an_error_report() -> None:
    doc = minimal()
    del doc["schema_version"]
    report = validate_palms(doc)
    assert not report.ok
    assert report.schema_version is None


@pytest.mark.parametrize("mode", ["read", "write"])
def test_major_2_raises(mode: str) -> None:
    with pytest.raises(ContractError, match="not supported"):
        validate_palms_file(PALMS / "invalid" / "major_2.geojson", mode=mode)  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", ["1", "v1.0", "1.0.0", 1.0])
def test_malformed_version_raises(bad: Any) -> None:
    doc = minimal()
    doc["schema_version"] = bad
    with pytest.raises(ContractError):
        validate_palms(doc)


def test_parse_and_check_version() -> None:
    assert parse_version("1.0") == (1, 0)
    assert parse_version("1.12") == (1, 12)
    for bad in ("1", "v1.0", "1.0.0"):
        with pytest.raises(ValueError):
            parse_version(bad)
    assert check_version("1.0") == "exact"
    assert check_version("1.3") == "newer_minor"
    with pytest.raises(ContractError):
        check_version("2.0")


def test_unparseable_json_is_one_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.geojson"
    path.write_text("{not json", encoding="utf-8")
    report = validate_palms_file(path)
    assert len(report.errors) == 1
    assert report.errors[0].path == ""


# --- semantic rules S1-S9, one test each -------------------------------------------------------


def test_s1_duplicate_palm_id() -> None:
    doc = two_features()
    doc["features"][1] = copy.deepcopy(doc["features"][0])
    assert "duplicate palm_id" in messages(validate_palms(doc))


def test_s2_feature_region_and_region_argument() -> None:
    doc = minimal()
    assert validate_palms(doc, region="san-diego").ok
    report = validate_palms(doc, region="los-angeles")
    assert [e.path for e in report.errors] == ["region"]
    doc["features"][0]["properties"]["region"] = "other"
    assert "does not match file region" in messages(validate_palms(doc))


def test_s3_mixed_prefix() -> None:
    doc = two_features()
    doc["features"][1]["id"] = doc["features"][1]["properties"]["palm_id"] = "abc-0000000000000002"
    assert "prefixes" in messages(validate_palms(doc))


def test_s4_id_mismatch() -> None:
    doc = minimal()
    doc["features"][0]["id"] = "sdc-00000000000000ff"
    assert "does not equal palm_id" in messages(validate_palms(doc))


def test_s5_bbox_argument() -> None:
    doc = minimal()
    lon, lat = doc["features"][0]["geometry"]["coordinates"]
    assert validate_palms(doc, bbox=(lon, lat, lon, lat)).ok  # edges inclusive
    report = validate_palms(doc, bbox=(0.0, 0.0, 1.0, 1.0))
    assert "outside bbox" in messages(report)
    assert report.errors[0].path == "features[0].geometry.coordinates"


def test_s6_radius_vs_crown() -> None:
    doc = minimal()
    props = doc["features"][0]["properties"]
    props.update(crown_diam_m=5.0, exclusion_radius_m=2.5)
    assert validate_palms(doc).ok  # equality is fine
    props["exclusion_radius_m"] = 2.4
    assert "less than half" in messages(validate_palms(doc))


@pytest.mark.parametrize(
    ("field", "value", "needed"),
    [
        ("height_source", "lidar", "lidar"),
        ("species_source", "inventory", "inventory"),
        ("species_source", "osm", "osm"),
    ],
)
def test_s7_source_requires_detector(field: str, value: str, needed: str) -> None:
    doc = minimal()
    props = doc["features"][0]["properties"]
    props["height_source"] = "species_default"
    props["species_source"] = "prior"
    props["detected_by"] = "lidar" if needed != "lidar" else "osm"
    props[field] = value
    assert f"does not include {needed!r}" in messages(validate_palms(doc))


def test_s8_null_ground_with_lidar_height_warns() -> None:
    doc = minimal()
    props = doc["features"][0]["properties"]
    props.update(height_source="lidar", detected_by="inventory+lidar", ground_elev_m=None)
    report = validate_palms(doc)
    assert report.ok
    assert [w.path for w in report.warnings] == ["features[0].properties.ground_elev_m"]
    props["ground_elev_m"] = 3.0
    assert validate_palms(doc).warnings == []


def test_s9_empty_features_warns() -> None:
    doc = minimal()
    doc["features"] = []
    report = validate_palms(doc)
    assert report.ok
    assert [w.path for w in report.warnings] == ["features"]


# --- report behaviour --------------------------------------------------------------------------


def test_max_errors_truncates() -> None:
    path = PALMS / "invalid" / "ten_bad_features.geojson"
    report = validate_palms_file(path, max_errors=3)
    assert len(report.errors) == 3
    assert report.truncated
    full = validate_palms_file(path)
    assert len(full.errors) == 10
    assert not full.truncated


def test_error_strings_format() -> None:
    report = validate_palms_file(PALMS / "invalid" / "ten_bad_features.geojson")
    strings = report.error_strings(limit=2)
    assert len(strings) == 2
    assert strings[0] == (
        "error features[0] sdc-0000000000000001: properties.height_m: "
        "-1 is less than the minimum of 0.5"
    )
    assert report.to_dict()["ok"] is False


def test_issue_str_without_palm_id_and_file_level() -> None:
    report = validate_palms_file(PALMS / "invalid" / "missing_palm_id.geojson")
    assert str(report.errors[0]).startswith("error features[0]: properties: ")
    file_level = validate_palms_file(PALMS / "invalid" / "missing_data_version.geojson")
    assert str(file_level.errors[0]).startswith("error file: ")


def test_raise_for_errors() -> None:
    validate_palms(minimal()).raise_for_errors()
    report = validate_palms_file(PALMS / "invalid" / "bad_palm_id.geojson")
    with pytest.raises(ContractError) as info:
        report.raise_for_errors()
    assert info.value.issues == report.errors


def test_issues_are_stable_and_sorted_by_path() -> None:
    doc = minimal()
    props = doc["features"][0]["properties"]
    props["height_m"] = -1
    props["crown_diam_m"] = 99
    paths = [e.path for e in validate_palms(doc).errors]
    assert paths == sorted(paths)
    assert paths == [e.path for e in validate_palms(doc).errors]


def test_older_valid_fixtures_still_pass() -> None:
    for path in sorted(PALMS.glob("valid_v1_*.geojson")):
        assert validate_palms_file(path).ok, path.name


# --- buildings ---------------------------------------------------------------------------------


def test_buildings_valid_and_invalid() -> None:
    assert validate_buildings(load(BUILDINGS / "valid_small.geojson")).ok
    dup = validate_buildings(load(BUILDINGS / "invalid_duplicate_id.geojson"))
    assert "duplicate building_id" in messages(dup)
    point = validate_buildings(load(BUILDINGS / "invalid_point_geometry.geojson"))
    assert not point.ok
    assert point.errors[0].path == "features[0].geometry.type"


def test_buildings_version_rules() -> None:
    doc = load(BUILDINGS / "valid_small.geojson")
    doc["schema_version"] = "2.0"
    with pytest.raises(ContractError):
        validate_buildings(doc)
    doc["schema_version"] = "1.4"
    report = validate_buildings(doc)
    assert report.ok
    assert len(report.warnings) == 1


@pytest.mark.slow
def test_ten_thousand_features_under_budget() -> None:
    doc = minimal()
    template = doc["features"][0]
    features = []
    for i in range(10_000):
        feature = copy.deepcopy(template)
        feature["id"] = feature["properties"]["palm_id"] = f"sdc-{i:016x}"
        features.append(feature)
    doc["features"] = features
    start = time.perf_counter()
    report = validate_palms(doc, mode="write")
    elapsed = time.perf_counter() - start
    assert report.ok
    assert report.feature_count == 10_000
    assert elapsed < 15


# --- review hardening --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad", ["garbageZ", "2026-11-21T12:00:00Z\n", "2026-11-21 12:00:00Z", "xZ"]
)
def test_generated_at_is_anchored(bad: str) -> None:
    doc = minimal()
    doc["generated_at"] = bad
    report = validate_palms(doc)
    assert [e.path for e in report.errors] == ["generated_at"]


def test_generated_at_accepts_fractional_seconds() -> None:
    doc = minimal()
    doc["generated_at"] = "2026-11-21T12:00:00.123Z"
    assert validate_palms(doc).ok


@pytest.mark.parametrize("bad", ["1.0\n", "1.0 ", " 1.0"])
def test_version_text_rejects_trailing_newline_and_space(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_version(bad)
    doc = minimal()
    doc["schema_version"] = bad
    with pytest.raises(ContractError):
        validate_palms(doc)


def test_schema_patterns_reject_trailing_newline() -> None:
    doc = minimal()
    doc["region"] = "san-diego\n"
    doc["data_version"] = "2026-11\n"
    doc["features"][0]["properties"]["palm_id"] = "sdc-0000000000000001\n"
    paths = {e.path for e in validate_palms(doc).errors}
    assert {"region", "data_version", "features[0].properties.palm_id"} <= paths
    # the schema pattern itself, with a version that only differs by the newline
    schema_version = load_schema("palms")["properties"]["schema_version"]["pattern"]
    assert re.search(schema_version, "1.0") is not None
    assert re.search(schema_version, "1.0\n") is None


def test_buildings_schema_version_rejects_trailing_newline() -> None:
    doc = load(BUILDINGS / "valid_small.geojson")
    doc["schema_version"] = "1.0\n"
    with pytest.raises(ContractError):
        validate_buildings(doc)
    doc["schema_version"] = "1.0"
    doc["region"] = "san-diego\n"
    assert [e.path for e in validate_buildings(doc).errors] == ["region"]


def test_buildings_schema_file_problems_raise_palmfix_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    doc = load(BUILDINGS / "valid_small.geojson")
    monkeypatch.setenv("PALMFIX_SCHEMA_DIR", str(tmp_path))
    contract._buildings_validators.cache_clear()
    try:
        with pytest.raises(PalmfixError, match="not found"):
            validate_buildings(doc)
        (tmp_path / "buildings.geojson.schema.json").write_text("{broken", encoding="utf-8")
        with pytest.raises(PalmfixError, match="not valid JSON"):
            validate_buildings(doc)
    finally:
        contract._buildings_validators.cache_clear()


def test_non_finite_numbers_are_rejected() -> None:
    text = (PALMS / "valid_minimal.geojson").read_text(encoding="utf-8")
    nan_doc = json.loads(text.replace("32.7157", "NaN"))
    report = validate_palms(nan_doc)
    assert any(
        e.path == "features[0].geometry.coordinates[1]" and "non-finite" in e.message
        for e in report.errors
    )
    inf_doc = json.loads(text.replace('"height_m": 12.5', '"height_m": Infinity'))
    assert not validate_palms(inf_doc).ok
    bbox_doc = minimal()
    bbox_doc["bbox"] = [-118.0, 32.0, float("inf"), 33.0]
    assert [e.path for e in validate_palms(bbox_doc).errors] == ["bbox[2]"]
    bld = load(BUILDINGS / "valid_small.geojson")
    bld["features"][0]["geometry"]["coordinates"][0][0][0] = float("nan")
    assert not validate_buildings(bld).ok
