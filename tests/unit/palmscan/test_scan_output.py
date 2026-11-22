"""palmscan.output: PalmRecord -> palms.geojson mapping, ids, validation and writing."""

from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path
from typing import Any

import pytest

from palmcore.errors import ContractError
from palmcore.palms import PalmsMeta
from palmscan.model import LidarCandidate, PalmRecord
from palmscan.output import (
    assign_palm_ids,
    to_feature_collection,
    validate_palms,
    write_invalid,
    write_palms,
)
from tests.helpers.contract import assert_palms_ok
from tests.helpers.fixtures import REPO_ROOT

EXPECTED = REPO_ROOT / "tests" / "fixtures" / "palmscan" / "output" / "expected_palms.geojson"
REGION = "test-region"
PREFIX = "tst"
META = PalmsMeta(
    schema_version="1.0",
    region=REGION,
    generated_at="2026-11-22T00:00:00Z",
    data_version="2026-11",
    generator_name="palmscan",
    generator_version="0.1.0",
    config_sha256=None,
)


def _candidate() -> LidarCandidate:
    return LidarCandidate(
        candidate_id="ds1:t7:3",
        dataset="ds1",
        x=481234.4,
        y=3622345.6,
        lon=-117.2,
        lat=32.75,
        height_m=14.04,
        crown_area_m2=20.0,
        crown_diam_m=5.05,
        ratio=2.8,
        shared_boundary_frac=0.1,
        ground_elev_m=12.34,
        accepted=True,
        vintage="2021",
    )


def make_records() -> list[PalmRecord]:
    return [
        # inventory, species-level, height from the record
        PalmRecord(
            stable_key="sd_street:100",
            lon=-117.1612345678,
            lat=32.7157,
            x=1.0,
            y=2.0,
            species="washingtonia_robusta",
            species_confidence=0.95,
            species_source="inventory",
            height_m=12.34,
            height_source="inventory",
            crown_diam_m=4.04,
            detected_by="inventory",
            source_ids=["sd_street:100"],
            data_vintage={"inventory": "2024"},
            exclusion_radius_m=2.5249,
        ),
        # genus-only name: two source ids given out of order
        PalmRecord(
            stable_key="sd_street:200",
            lon=-117.17,
            lat=32.72,
            x=3.0,
            y=4.0,
            species="phoenix_unknown",
            species_confidence=0.8,
            species_source="inventory",
            height_m=8.0,
            height_source="species_default",
            crown_diam_m=5.0,
            detected_by="inventory+osm",
            source_ids=["sd_street:200", "osm:node/5"],
            data_vintage={"osm": "2026-10", "inventory": "2024"},
            exclusion_radius_m=3.0,
        ),
        # species drawn from the priors
        PalmRecord(
            stable_key="osm:node/9",
            lon=-117.18,
            lat=32.73,
            x=5.0,
            y=6.0,
            species="washingtonia_robusta",
            species_confidence=0.3,
            species_source="prior",
            height_m=11.0,
            height_source="species_default",
            crown_diam_m=4.0,
            detected_by="osm",
            source_ids=["osm:node/9"],
            data_vintage={"osm": "2026-10"},
            exclusion_radius_m=2.5,
        ),
        # building conflict, ground elevation known
        PalmRecord(
            stable_key="sd_street:300",
            lon=-117.19,
            lat=32.74,
            x=7.0,
            y=8.0,
            species="phoenix_canariensis",
            species_confidence=0.95,
            species_source="inventory",
            height_m=9.0,
            height_source="inventory",
            crown_diam_m=6.0,
            ground_elev_m=35.26,
            detected_by="inventory",
            source_ids=["sd_street:300"],
            data_vintage={"inventory": "2024", "buildings": "2023"},
            exclusion_radius_m=3.5,
            building_conflict=True,
        ),
        # LiDAR only: the candidate id is not a stable source id
        PalmRecord(
            stable_key="lidar:ds1:t7:3",
            lon=-117.2,
            lat=32.75,
            x=481234.4,
            y=3622345.6,
            species="washingtonia_robusta",
            species_confidence=0.7,
            species_source="lidar_rules",
            height_m=14.04,
            height_source="lidar",
            crown_diam_m=5.05,
            ground_elev_m=12.34,
            detected_by="lidar",
            source_ids=["lidar:ds1:t7:3"],
            data_vintage={"lidar": "2021"},
            exclusion_radius_m=3.0,
            lidar=_candidate(),
        ),
    ]


def build(records: list[PalmRecord]) -> dict[str, Any]:
    return to_feature_collection(records, REGION, id_prefix=PREFIX, meta=META)


def test_golden_bytes(tmp_path: Path) -> None:
    out = tmp_path / "palms.geojson"
    write_palms(build(make_records()), out)
    assert out.read_bytes() == EXPECTED.read_bytes()


def test_shuffled_input_gives_identical_file(tmp_path: Path) -> None:
    reference = tmp_path / "a.geojson"
    write_palms(build(make_records()), reference)
    for seed in range(5):
        records = make_records()
        random.Random(seed).shuffle(records)
        for rec in records:
            rec.source_ids.reverse()
        out = tmp_path / f"b{seed}.geojson"
        write_palms(build(records), out)
        assert out.read_bytes() == reference.read_bytes()


def test_ids_are_stable_and_follow_the_key_rules() -> None:
    records = make_records()
    ids_a = assign_palm_ids(records, PREFIX)
    ids_b = assign_palm_ids(list(reversed(records)), PREFIX)
    assert ids_a == list(reversed(ids_b))
    assert all(i.startswith("tst-") and len(i) == 20 for i in ids_a)
    # the LiDAR candidate id is ignored; moving the lidar-only palm by <0.5 m keeps its id
    lidar = dataclasses.replace(records[4], x=481234.2, y=3622345.8)
    assert assign_palm_ids([lidar], PREFIX)[0] == ids_a[4]
    # a merged inventory+lidar palm keeps the inventory id
    merged = dataclasses.replace(
        records[0], source_ids=["sd_street:100", "lidar:ds1:t7:3"], lidar=_candidate()
    )
    assert assign_palm_ids([merged], PREFIX)[0] == ids_a[0]


def test_duplicate_stable_key_is_reported() -> None:
    a, b = make_records()[:2]
    b.source_ids = ["sd_street:100", "sd_street:999"]
    b.stable_key = "other"
    with pytest.raises(ContractError) as info:
        assign_palm_ids([a, b], PREFIX)
    message = str(info.value)
    assert "sd_street:100" in message
    assert "other" in message


def test_every_fixture_feature_validates() -> None:
    fc = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert len(fc["features"]) == 5
    assert validate_palms(fc) == []
    assert_palms_ok(EXPECTED)


def test_written_file_passes_contract_helper(tmp_path: Path) -> None:
    out = tmp_path / "palms.geojson"
    write_palms(build(make_records()), out)
    assert_palms_ok(out)
    doc = json.loads(out.read_text(encoding="utf-8"))
    ids = [f["properties"]["palm_id"] for f in doc["features"]]
    assert ids == sorted(ids)


def test_negative_height_is_rejected(tmp_path: Path) -> None:
    records = make_records()
    records[0].height_m = -3.0
    fc = build(records)
    errors = validate_palms(fc)
    assert errors
    assert any("height_m" in e for e in errors)
    out = tmp_path / "palms.geojson"
    with pytest.raises(ContractError):
        write_palms(fc, out)
    assert not out.exists()
    invalid = write_invalid(fc, tmp_path)
    assert invalid.name == "palms.invalid.geojson"
    assert json.loads(invalid.read_text(encoding="utf-8"))["features"]


def test_missing_species_is_reported_not_guessed() -> None:
    records = make_records()
    records[1].species = None
    errors = validate_palms(build(records))
    assert errors
    assert any("species" in e for e in errors)


def test_region_mismatch_is_a_value_error() -> None:
    with pytest.raises(ValueError):
        to_feature_collection(make_records(), "other", id_prefix=PREFIX, meta=META)
