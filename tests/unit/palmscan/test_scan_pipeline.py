"""palmscan run / priors end to end on the offline e2e fixture region (SCAN-013)."""

from __future__ import annotations

import csv
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from palmcore import contract
from palmscan import pipeline
from palmscan.cli import main
from tests.helpers.contract import assert_palms_ok
from tests.helpers.fixtures import FIXTURES_ROOT

REGIONS_DIR = FIXTURES_ROOT / "palmscan" / "regions"
E2E_YAML = REGIONS_DIR / "e2e.yaml"
OUTPUTS = (
    "palms.geojson",
    "buildings.geojson",
    "species_priors.yaml",
    "qa_summary.md",
    "qa_map.gpkg",
    "qa_rejects.csv",
    "run.json",
)
Region = Callable[[Callable[[dict[str, Any]], None]], Path]


@pytest.fixture(autouse=True)
def _fixed_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1795000000")


def _run_args(tmp_path: Path, region: str = "e2e", regions_dir: Path = REGIONS_DIR) -> list[str]:
    return [
        "run",
        "--region",
        region,
        "--regions-dir",
        str(regions_dir),
        "--out",
        str(tmp_path / "out"),
        "--data-dir",
        str(tmp_path / "data"),
        "--offline",
        "--no-log-file",
    ]


@pytest.fixture
def make_region(tmp_path: Path) -> Region:
    """Write a tweaked copy of e2e.yaml into ``tmp_path/regions`` and return that directory."""

    def make(edit: Callable[[dict[str, Any]], None]) -> Path:
        data = yaml.safe_load(E2E_YAML.read_text(encoding="utf-8"))
        for source in data["sources"]["inventory"]:
            source["path"] = str((REGIONS_DIR.parent / source["path"]).resolve())
        data["sources"]["buildings_path"] = str(
            (REGIONS_DIR.parent / data["sources"]["buildings_path"]).resolve()
        )
        edit(data)
        directory = tmp_path / "regions"
        directory.mkdir(exist_ok=True)
        (directory / "e2e.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
        return directory

    return make


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def test_e2e_run_writes_every_output(tmp_path: Path) -> None:
    assert main(_run_args(tmp_path)) == 0
    out = tmp_path / "out"
    for name in OUTPUTS:
        assert (out / name).is_file(), name

    palms = _load(out / "palms.geojson")
    assert_palms_ok(palms, region=E2E_YAML)
    feats = palms["features"]
    assert len(feats) == 13  # 17 records: vacant, oak, one duplicate and one masked are gone
    source_ids = {s for f in feats for s in f["properties"]["source_ids"]}
    assert "e2e_trees:7" not in source_ids  # vacant site
    assert "e2e_trees:8" not in source_ids  # oak
    assert "e2e_trees:10" not in source_ids  # inside the mask
    merged = next(f for f in feats if "e2e_second:1" in f["properties"]["source_ids"])
    assert merged["properties"]["source_ids"] == ["e2e_second:1", "e2e_trees:1"]
    assert merged["properties"]["species"] == "washingtonia_robusta"
    assert merged["properties"]["species_source"] == "inventory"
    sampled = next(f for f in feats if f["properties"]["source_ids"] == ["e2e_trees:9"])
    assert sampled["properties"]["species_source"] == "prior"
    assert sampled["properties"]["species_confidence"] == 0.3
    assert sum(f["properties"]["building_conflict"] for f in feats) == 1

    with (out / "qa_rejects.csv").open(encoding="utf-8", newline="") as handle:
        rejects = list(csv.DictReader(handle))
    reasons = {(r["stage"], r["reason"]) for r in rejects}
    assert ("mask", "mask_out:e2e_no_go") in reasons
    assert ("inventory", "vacant") in reasons
    assert any(stage == "dedupe" for stage, _ in reasons)

    run = _load(out / "run.json")
    assert run["exit_code"] == 0
    assert run["counts"]["palms"] == 13
    assert run["counts"]["building_conflicts"] == 1
    assert set(run["stage_seconds"]) >= {"ingest_inventory", "dedupe", "write_palms"}
    assert (out / "qa_summary.md").read_text(encoding="utf-8").startswith("# palmscan QA: e2e")


def test_buildings_geojson_holds_nearby_footprints(tmp_path: Path) -> None:
    assert main(_run_args(tmp_path)) == 0
    doc = _load(tmp_path / "out" / "buildings.geojson")
    assert contract.validate_buildings(doc).errors == []
    assert doc["schema_version"] == "1.0"
    assert doc["region"] == "e2e"
    ids = [f["properties"]["building_id"] for f in doc["features"]]
    # msbf:0 conflicts with a palm, msbf:1 is 6 m from one (inside radius_max + clip_buffer),
    # msbf:2 is far from every palm and is left out.
    assert ids == ["msbf:0", "msbf:1"]
    assert doc["notices"]["microsoft_footprints"]["license"] == "CDLA-Permissive-2.0"


def test_second_run_is_byte_identical(tmp_path: Path) -> None:
    assert main(_run_args(tmp_path)) == 0
    out = tmp_path / "out"
    first = (out / "palms.geojson").read_bytes()
    first_buildings = (out / "buildings.geojson").read_bytes()
    (out / "palms.geojson").unlink()
    assert main(_run_args(tmp_path)) == 0
    assert (out / "palms.geojson").read_bytes() == first
    assert (out / "buildings.geojson").read_bytes() == first_buildings


def test_priors_command_prints_yaml(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = [
        "priors",
        "--region",
        "e2e",
        "--regions-dir",
        str(REGIONS_DIR),
        "--data-dir",
        str(tmp_path / "data"),
        "--offline",
        "--no-log-file",
    ]
    assert main(argv) == 0
    block = yaml.safe_load(capsys.readouterr().out)
    priors = block["species_priors"]
    assert priors["washingtonia_robusta"] > 0
    assert "brahea_sp" not in priors  # genus-only names are not species-level priors
    assert sum(priors.values()) == pytest.approx(1.0)


def test_bad_config_exits_2(tmp_path: Path, make_region: Region) -> None:
    def edit(data: dict[str, Any]) -> None:
        data["palmscan"] = {"dedupe_radius": 3}

    assert main(_run_args(tmp_path, regions_dir=make_region(edit))) == 2
    assert main(_run_args(tmp_path, region="no-such-region")) == 2


def test_offline_cache_miss_exits_5(tmp_path: Path, make_region: Region) -> None:
    def edit(data: dict[str, Any]) -> None:
        source = data["sources"]["inventory"][0]
        del source["path"]
        source["url"] = "https://example.invalid/trees.geojson"
        data["sources"]["inventory"] = [source]

    assert main(_run_args(tmp_path, regions_dir=make_region(edit))) == 5
    run = _load(tmp_path / "out" / "run.json")
    assert run["exit_code"] == 5
    assert not (tmp_path / "out" / "palms.geojson").exists()


def test_missing_inventory_file_exits_4(tmp_path: Path, make_region: Region) -> None:
    def edit(data: dict[str, Any]) -> None:
        data["sources"]["inventory"][0]["path"] = str(tmp_path / "missing.geojson")

    assert main(_run_args(tmp_path, regions_dir=make_region(edit))) == 4


def test_validation_failure_exits_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "validate_palms", lambda fc: ["forced failure"])
    assert main(_run_args(tmp_path)) == 3
    out = tmp_path / "out"
    assert (out / "palms.invalid.geojson").is_file()
    assert not (out / "palms.geojson").exists()
    assert _load(out / "run.json")["exit_code"] == 3


def test_lidar_source_warns_and_continues(tmp_path: Path, make_region: Region) -> None:
    def edit(data: dict[str, Any]) -> None:
        data["sources"]["lidar"] = "3dep_ept"

    assert main(_run_args(tmp_path, regions_dir=make_region(edit))) == 0
    run = _load(tmp_path / "out" / "run.json")
    assert "LiDAR stage not implemented yet; inventory only" in run["warnings"]

    assert main([*_run_args(tmp_path, regions_dir=make_region(edit)), "--no-lidar"]) == 0
    run = _load(tmp_path / "out" / "run.json")
    assert run["warnings"] == []


def test_default_output_dir_is_build_scan_region(tmp_path: Path) -> None:
    argv = [
        "run",
        "--region",
        "e2e",
        "--regions-dir",
        str(REGIONS_DIR),
        "--build-dir",
        str(tmp_path / "build"),
        "--data-dir",
        str(tmp_path / "data"),
        "--offline",
        "--no-log-file",
    ]
    assert main(argv) == 0
    assert (tmp_path / "build" / "scan" / "e2e" / "palms.geojson").is_file()
