from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.fixtures import (
    FIXTURES_ROOT,
    REPO_ROOT,
    copy_fixture_tree,
    fixture_path,
    load_bytes,
    load_geojson,
    load_json,
    load_text,
    load_yaml,
)


def test_roots() -> None:
    assert (REPO_ROOT / "pyproject.toml").is_file()
    assert FIXTURES_ROOT == REPO_ROOT / "tests" / "fixtures"


def test_loaders_on_samples() -> None:
    assert load_json("helpers", "sample.json") == {"name": "sample", "values": [1, 2, 3]}
    assert load_yaml("helpers", "sample.yaml") == {"name": "sample", "values": [1, 2]}
    assert load_text("helpers", "tree/a.txt").strip() == "a"
    assert load_bytes("helpers", "tree/a.txt").strip() == b"a"
    gj = load_geojson("helpers", "sample.geojson")
    assert gj["geometry"]["type"] == "Point"


def test_missing_file_names_path_and_lists_siblings() -> None:
    with pytest.raises(FileNotFoundError) as exc:
        fixture_path("helpers", "nope.json")
    msg = str(exc.value)
    assert str(FIXTURES_ROOT / "helpers" / "nope.json") in msg
    assert "sample.json" in msg


def test_missing_package_dir() -> None:
    with pytest.raises(FileNotFoundError, match="no_such_pkg"):
        load_text("no_such_pkg", "x.txt")


def test_load_geojson_rejects_non_geojson() -> None:
    with pytest.raises(AssertionError, match="not GeoJSON"):
        load_geojson("helpers", "sample.json")


def test_copy_fixture_tree(tmp_path: Path) -> None:
    out = copy_fixture_tree("helpers", "tree", tmp_path)
    assert out == tmp_path / "tree"
    assert (out / "a.txt").read_text().strip() == "a"
    assert (out / "sub" / "b.txt").read_text().strip() == "b"


def test_copy_fixture_tree_rejects_file(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        copy_fixture_tree("helpers", "sample.json", tmp_path)
