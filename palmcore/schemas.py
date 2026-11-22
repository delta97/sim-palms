"""Locate and load the JSON schema files, and build validators for them."""

from __future__ import annotations

import functools
import importlib.resources
import json
import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, cast

import jsonschema
from jsonschema import Draft202012Validator

from palmcore.errors import ConfigError, PalmfixError

SCHEMA_FILES: Final = {
    "palms": "palms.geojson.schema.json",
    "region": "region.schema.json",
}

_SCHEMA_NAME_RE: Final = re.compile(r"^[a-z0-9-]+\.schema\.json$")
_ENV_VAR: Final = "PALMFIX_SCHEMA_DIR"


def schema_dir() -> Path:
    """Return the schema directory: env override, source checkout, then installed wheel."""
    override = os.environ.get(_ENV_VAR)
    if override:
        path = Path(override)
        if not path.is_dir():
            raise ConfigError(f"{_ENV_VAR} is set but is not a directory: {path}")
        return path

    candidates = [
        Path(__file__).resolve().parents[1] / "schemas",
        Path(str(importlib.resources.files("palmcore") / "_schemas")),
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    tried = ", ".join(str(c) for c in candidates)
    raise PalmfixError(f"schema directory not found; tried: {tried}")


@functools.cache
def load_schema(name: str) -> dict[str, Any]:
    """Load a schema by SCHEMA_FILES key or by file name. Callers must not mutate the result."""
    # Mapped keys may name files (palms.geojson.schema.json) that the pattern would reject.
    file_name = SCHEMA_FILES.get(name)
    if file_name is None:
        if not _SCHEMA_NAME_RE.match(name):
            raise ValueError(f"invalid schema name: {name!r}")
        file_name = name
    path = schema_dir() / file_name
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise PalmfixError(f"schema file not found: {path}") from exc
    try:
        return cast("dict[str, Any]", json.loads(text))
    except json.JSONDecodeError as exc:
        raise PalmfixError(f"schema file is not valid JSON: {path}: {exc}") from exc


def make_validator(schema: Mapping[str, Any]) -> jsonschema.Draft202012Validator:
    """Check the schema itself, then build a Draft 2020-12 validator with format checking."""
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
