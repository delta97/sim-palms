import json
from collections.abc import Iterator
from pathlib import Path

import jsonschema
import pytest

from palmcore import schemas
from palmcore.errors import ConfigError, PalmfixError


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    schemas.load_schema.cache_clear()
    yield
    schemas.load_schema.cache_clear()


@pytest.fixture
def schema_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("PALMFIX_SCHEMA_DIR", str(tmp_path))
    return tmp_path


def test_load_by_key_and_by_file_name(schema_root: Path) -> None:
    (schema_root / "palms.geojson.schema.json").write_text('{"title": "palms"}', encoding="utf-8")
    (schema_root / "extra.schema.json").write_text('{"title": "extra"}', encoding="utf-8")
    assert schemas.load_schema("palms") == {"title": "palms"}
    assert schemas.load_schema("extra.schema.json") == {"title": "extra"}


def test_schema_dir_uses_env_override(schema_root: Path) -> None:
    assert schemas.schema_dir() == schema_root


@pytest.mark.parametrize("bad", ["../x", "x.json", "UPPER.schema.json", "a/b.schema.json"])
def test_invalid_names_raise_value_error(schema_root: Path, bad: str) -> None:
    with pytest.raises(ValueError, match="invalid schema name"):
        schemas.load_schema(bad)


def test_missing_file_names_full_path(schema_root: Path) -> None:
    with pytest.raises(PalmfixError, match=r"region\.schema\.json"):
        schemas.load_schema("region")


def test_invalid_json_raises(schema_root: Path) -> None:
    (schema_root / "region.schema.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(PalmfixError, match="not valid JSON"):
        schemas.load_schema("region")


def test_nonexistent_env_dir_is_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PALMFIX_SCHEMA_DIR", str(tmp_path / "missing"))
    with pytest.raises(ConfigError):
        schemas.schema_dir()


def test_default_schema_dir_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PALMFIX_SCHEMA_DIR", raising=False)
    repo_schemas = Path(schemas.__file__).resolve().parents[1] / "schemas"
    if repo_schemas.is_dir():
        assert schemas.schema_dir() == repo_schemas
    else:
        with pytest.raises(PalmfixError, match="schema directory not found"):
            schemas.schema_dir()


def test_make_validator_valid_and_invalid_schema() -> None:
    validator = schemas.make_validator({"type": "object", "required": ["a"]})
    assert not validator.is_valid({})
    assert validator.is_valid({"a": 1})
    with pytest.raises(jsonschema.SchemaError):
        schemas.make_validator({"type": 5})


def test_make_validator_checks_formats() -> None:
    validator = schemas.make_validator({"type": "string", "format": "date"})
    assert validator.is_valid("2026-11-22")
    assert not validator.is_valid("not-a-date")


def test_loaded_schema_roundtrips_json(schema_root: Path) -> None:
    doc = {"type": "object"}
    (schema_root / "region.schema.json").write_text(json.dumps(doc), encoding="utf-8")
    assert schemas.load_schema("region") == doc
