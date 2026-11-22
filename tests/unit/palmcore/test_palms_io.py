"""palms.geojson reader, writer and canonical serializer (ARCH-007)."""

from __future__ import annotations

import json
import logging
import random
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from palmcore.contract import validate_palms
from palmcore.errors import ContractError
from palmcore.palms import Palm, dump_palms, read_palms, write_palms, write_palms_doc
from tests.helpers.fixtures import FIXTURES_ROOT

SAMPLE = FIXTURES_ROOT / "palmcore" / "palms_io" / "sample_10.geojson"
NEWER_MINOR = FIXTURES_ROOT / "palmcore" / "palms" / "newer_minor_1_1.geojson"
STAMP = datetime(2026, 1, 1, tzinfo=UTC)
WRITE_ARGS: dict[str, Any] = {
    "region": "san-diego",
    "generator_name": "palmscan",
    "generator_version": "0.1.0",
    "config_sha256": None,
    "generated_at": STAMP,
}

_DETECTED = (
    "inventory",
    "osm",
    "lidar",
    "inventory+osm",
    "inventory+lidar",
    "osm+lidar",
    "inventory+osm+lidar",
)


def make_palm(i: int, **overrides: Any) -> Palm:
    detected = _DETECTED[i % len(_DETECTED)]
    parts = detected.split("+")
    base = Palm(
        palm_id=f"sdc-{i:016x}",
        lon=round(-117.161 + i * 0.0001, 7),
        lat=round(32.7157 + i * 0.00005, 7),
        species="washingtonia_robusta" if i % 2 == 0 else "phoenix_canariensis",
        species_confidence=round(0.5 + i * 0.05, 2),
        species_source="inventory" if "inventory" in parts else "prior",
        height_m=round(8.0 + i * 1.5, 1),
        height_source="lidar" if "lidar" in parts else "species_default",
        crown_diam_m=round(3.0 + i * 0.3, 1),
        ground_elev_m=None if i == 3 else 10.0 + i,
        detected_by=detected,
        source_ids=tuple(sorted(f"{p}:{i}" for p in parts)),
        exclusion_radius_m=round(3.5 + i * 0.25, 2),
        building_conflict=i % 4 == 0,
        data_vintage={"inventory": "2024-05", "lidar": "2021"},
        region="san-diego",
        extra={"x_note": "hand checked"} if i == 5 else {},
    )
    return replace(base, **overrides)


def sample_palms() -> list[Palm]:
    return [make_palm(i) for i in range(1, 11)]


def test_sample_helper_covers_every_detected_by() -> None:
    palms = sample_palms()
    assert {p.detected_by for p in palms} == set(_DETECTED)
    assert sum(p.ground_elev_m is None for p in palms) == 1
    assert sum(bool(p.extra) for p in palms) == 1


def test_write_read_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "out" / "palms.geojson"  # parent dirs are created
    meta = write_palms(path, sample_palms(), **WRITE_ARGS)
    got = read_palms(path)
    assert got.palms == sample_palms()
    assert got.meta == meta
    assert got.report.ok
    assert got.by_id()["sdc-0000000000000005"].extra == {"x_note": "hand checked"}
    assert got.by_id()["sdc-0000000000000003"].ground_elev_m is None


def test_input_order_does_not_change_bytes(tmp_path: Path) -> None:
    palms = sample_palms()
    shuffled = palms[:]
    random.Random(7).shuffle(shuffled)
    a, b = tmp_path / "a.geojson", tmp_path / "b.geojson"
    write_palms(a, palms, **WRITE_ARGS)
    write_palms(b, shuffled, **WRITE_ARGS)
    assert a.read_bytes() == b.read_bytes()
    assert b"\r" not in a.read_bytes()


def test_matches_committed_sample(tmp_path: Path) -> None:
    out = tmp_path / "sample.geojson"
    write_palms(out, sample_palms(), **WRITE_ARGS)
    assert out.read_bytes() == SAMPLE.read_bytes()


def test_sample_is_valid_and_readable() -> None:
    got = read_palms(SAMPLE)
    assert len(got.palms) == 10
    assert (got.meta.schema_version, got.meta.data_version) == ("1.0", "2026-01")
    assert got.meta.generated_at == "2026-01-01T00:00:00Z"
    assert got.meta.to_dict()["data_version"] == "2026-01"


def test_rounding_and_negative_zero(tmp_path: Path) -> None:
    palm = make_palm(
        1,
        lon=-117.253112345,
        lat=-0.0,
        height_m=22.46,
        exclusion_radius_m=3.456,
        species_confidence=0.954,
        crown_diam_m=4.0,
        ground_elev_m=-0.0,
    )
    path = tmp_path / "r.geojson"
    write_palms(path, [palm], **WRITE_ARGS)
    text = path.read_text(encoding="utf-8")
    feature = json.loads(text)["features"][0]
    props = feature["properties"]
    assert feature["geometry"]["coordinates"] == [-117.2531123, 0.0]
    assert props["height_m"] == 22.5
    assert props["exclusion_radius_m"] == 3.46
    assert props["species_confidence"] == 0.95
    assert props["ground_elev_m"] == 0.0
    assert "-0.0" not in text


def test_source_ids_sorted(tmp_path: Path) -> None:
    palm = make_palm(7, source_ids=("osm:2", "inventory:9", "lidar:1"))
    path = tmp_path / "s.geojson"
    write_palms(path, [palm], **WRITE_ARGS)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["features"][0]["properties"]["source_ids"] == ["inventory:9", "lidar:1", "osm:2"]


def test_key_order_and_feature_id(tmp_path: Path) -> None:
    path = tmp_path / "k.geojson"
    write_palms(path, [make_palm(5)], **WRITE_ARGS)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert list(doc) == [
        "type",
        "schema_version",
        "region",
        "generated_at",
        "data_version",
        "generator",
        "config_sha256",
        "features",
    ]
    feature = doc["features"][0]
    assert list(feature) == ["type", "id", "geometry", "properties"]
    assert feature["id"] == feature["properties"]["palm_id"]
    assert list(feature["properties"])[-2:] == ["region", "x_note"]


def test_nan_raises_and_writes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "nan.geojson"
    with pytest.raises(ContractError):
        write_palms(path, [make_palm(1, height_m=float("nan"))], **WRITE_ARGS)
    with pytest.raises(ContractError):
        write_palms(path, [make_palm(1, lon=float("inf"))], **WRITE_ARGS)
    assert not path.exists()


def test_invalid_palm_leaves_existing_file_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "keep.geojson"
    write_palms(path, sample_palms(), **WRITE_ARGS)
    before = path.read_bytes()
    bad = make_palm(1, crown_diam_m=10.0, exclusion_radius_m=2.0)  # radius < crown / 2
    with pytest.raises(ContractError):
        write_palms(path, [bad], **WRITE_ARGS)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_write_palms_doc_rejects_invalid_doc(tmp_path: Path) -> None:
    path = tmp_path / "doc.geojson"
    with pytest.raises(ContractError):
        write_palms_doc(path, {"type": "FeatureCollection", "schema_version": "1.0"})
    assert not path.exists()


def test_empty_input_writes_valid_file_and_read_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "empty.geojson"
    write_palms(path, [], **WRITE_ARGS)
    assert validate_palms(json.loads(path.read_text(encoding="utf-8"))).ok
    with caplog.at_level(logging.WARNING, logger="palmfix.palmcore.palms"):
        got = read_palms(path)
    assert got.palms == []
    assert len([r for r in caplog.records if r.levelno == logging.WARNING]) == 1


def test_newer_minor_keeps_unknown_fields(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="palmfix.palmcore.palms"):
        got = read_palms(NEWER_MINOR)
    assert got.palms[0].extra == {"canopy_class": "dense"}
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "1.1" in warnings[0].getMessage()


def test_read_without_validation_still_checks_version(tmp_path: Path) -> None:
    got = read_palms(SAMPLE, validate=False)
    assert len(got.palms) == 10
    major2 = tmp_path / "v2.geojson"
    text = SAMPLE.read_text(encoding="utf-8").replace(
        '"schema_version": "1.0"', '"schema_version": "2.0"'
    )
    major2.write_text(text, encoding="utf-8")
    with pytest.raises(ContractError):
        read_palms(major2, validate=False)


def test_read_rejects_invalid_file(tmp_path: Path) -> None:
    path = tmp_path / "bad.geojson"
    text = SAMPLE.read_text(encoding="utf-8").replace("san-diego", "elsewhere", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ContractError):
        read_palms(path)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ContractError):
        read_palms(path)


def test_source_date_epoch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767225600")
    path = tmp_path / "epoch.geojson"
    meta = write_palms(
        path,
        sample_palms(),
        region="san-diego",
        generator_name="palmscan",
        generator_version="0.1.0",
    )
    assert (meta.generated_at, meta.data_version) == ("2026-01-01T00:00:00Z", "2026-01")
    assert path.read_bytes() == SAMPLE.read_bytes()


def test_explicit_arguments_beat_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1767225600")
    args = {**WRITE_ARGS, "generated_at": datetime(2027, 3, 4, 5, 6, 7, 999, tzinfo=UTC)}
    meta = write_palms(tmp_path / "x.geojson", sample_palms(), data_version="2026-11", **args)
    assert (meta.generated_at, meta.data_version) == ("2027-03-04T05:06:07Z", "2026-11")


def test_dump_is_idempotent() -> None:
    text = SAMPLE.read_text(encoding="utf-8")
    assert dump_palms(json.loads(text)) == text
    assert text.endswith("}\n")
