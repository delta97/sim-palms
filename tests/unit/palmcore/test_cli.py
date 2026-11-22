from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from palmcore.cli import main
from palmcore.log import LOGGER_ROOT
from tests.helpers.fixtures import fixture_path

REGIONS = "regions"


def _reset_logging() -> None:
    for lg in (logging.getLogger(), logging.getLogger(LOGGER_ROOT)):
        for h in list(lg.handlers):
            if lg.name == LOGGER_ROOT or getattr(h, "_palmfix", False):
                lg.removeHandler(h)
                h.close()
    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger(LOGGER_ROOT).setLevel(logging.NOTSET)


@pytest.fixture(autouse=True)
def _clean_logging() -> Iterator[None]:
    _reset_logging()
    yield
    _reset_logging()


def _run(tmp_path: Path, *argv: str) -> int:
    return main([*argv, "--build-dir", str(tmp_path)])


def test_validate_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sample = fixture_path("palmcore", "palms_io/sample_10.geojson")
    assert _run(tmp_path, "validate", str(sample)) == 0
    out = capsys.readouterr().out
    assert "OK: 10 features" in out
    assert "schema 1.0" in out


def test_validate_invalid_exits_3(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = fixture_path("palmcore", "palms/invalid/duplicate_palm_id.geojson")
    assert _run(tmp_path, "validate", str(bad)) == 3
    out = capsys.readouterr().out
    assert "error features[" in out
    assert "FAILED:" in out


def test_validate_json_only_on_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bad = fixture_path("palmcore", "palms/invalid/duplicate_palm_id.geojson")
    assert _run(tmp_path, "validate", str(bad), "--json") == 3
    doc = json.loads(capsys.readouterr().out)
    assert doc["ok"] is False
    assert doc["issues"]


def test_validate_empty_strict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty = fixture_path("palmcore", "palms/valid_empty.geojson")
    assert _run(tmp_path, "validate", str(empty)) == 0
    assert "OK: 0 features" in capsys.readouterr().out
    assert _run(tmp_path, "validate", str(empty), "--strict") == 3
    assert "FAILED" in capsys.readouterr().out


def test_validate_prints_at_most_50_issues(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = {
        "type": "FeatureCollection",
        "schema_version": "1.0",
        "features": [{"type": "Feature"}] * 120,
    }
    path = tmp_path / "many.geojson"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert _run(tmp_path, "validate", str(path)) == 3
    lines = capsys.readouterr().out.splitlines()
    assert sum(line.startswith("error ") for line in lines) == 50
    assert any(line.startswith("... and ") and line.endswith(" more") for line in lines)


def test_validate_missing_file_exits_2(tmp_path: Path) -> None:
    assert _run(tmp_path, "validate", str(tmp_path / "nope.geojson")) == 2


def test_validate_unknown_region_exits_2(tmp_path: Path) -> None:
    sample = fixture_path("palmcore", "palms_io/sample_10.geojson")
    regions = fixture_path("palmcore", REGIONS)
    code = _run(
        tmp_path, "validate", str(sample), "--region", "nowhere", "--regions-dir", str(regions)
    )
    assert code == 2


def test_regions_lists_fixtures(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    regions = fixture_path("palmcore", REGIONS)
    assert _run(tmp_path, "regions", "--regions-dir", str(regions)) == 0
    out = capsys.readouterr().out
    assert "full" in out
    assert "minimal" in out


def test_regions_check_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    regions = fixture_path("palmcore", REGIONS)
    code = _run(tmp_path, "regions", "--check", "--regions-dir", str(regions))
    assert code == 0
    assert capsys.readouterr().out.startswith("OK: 2 regions")


def test_regions_check_duplicate_prefix_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dup = fixture_path("palmcore", f"{REGIONS}/dup_prefix")
    assert _run(tmp_path, "regions", "--check", "--regions-dir", str(dup)) == 2
    assert "id_prefix" in capsys.readouterr().out


def test_config_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    regions = fixture_path("palmcore", REGIONS)
    code = _run(
        tmp_path, "config", "--region", "minimal", "--regions-dir", str(regions), "--format", "json"
    )
    assert code == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["exclusion"]["margin_m"] == 1.5
    assert doc["region"] == "minimal"


def test_config_yaml(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    regions = fixture_path("palmcore", REGIONS)
    assert _run(tmp_path, "config", "--region", "full", "--regions-dir", str(regions)) == 0
    assert "id_prefix:" in capsys.readouterr().out


def test_config_unknown_region_exits_2(tmp_path: Path) -> None:
    regions = fixture_path("palmcore", REGIONS)
    assert _run(tmp_path, "config", "--region", "nowhere", "--regions-dir", str(regions)) == 2


def test_config_requires_region(tmp_path: Path) -> None:
    assert _run(tmp_path, "config") == 2


def test_no_subcommand_returns_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "usage:" in capsys.readouterr().out
