"""Fixture loaders: recorded inputs live in ``tests/fixtures/<package>/``."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml


def _find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise RuntimeError(f"no pyproject.toml found above {start}")


REPO_ROOT: Path = _find_repo_root(Path(__file__).resolve().parent)
FIXTURES_ROOT: Path = REPO_ROOT / "tests" / "fixtures"


def fixture_path(package: str, name: str) -> Path:
    """Return the path of ``tests/fixtures/<package>/<name>``; raise if it does not exist."""
    path = FIXTURES_ROOT / package / name
    if not path.exists():
        pkg_dir = FIXTURES_ROOT / package
        existing = (
            sorted(p.relative_to(pkg_dir).as_posix() for p in pkg_dir.rglob("*") if p.is_file())[
                :10
            ]
            if pkg_dir.is_dir()
            else []
        )
        listing = ", ".join(existing) if existing else "(none)"
        raise FileNotFoundError(f"fixture not found: {path}; files in {pkg_dir}: {listing}")
    return path


def load_text(package: str, name: str, encoding: str = "utf-8") -> str:
    return fixture_path(package, name).read_text(encoding=encoding)


def load_bytes(package: str, name: str) -> bytes:
    return fixture_path(package, name).read_bytes()


def load_json(package: str, name: str) -> Any:
    return json.loads(load_text(package, name))


def load_yaml(package: str, name: str) -> Any:
    return yaml.safe_load(load_text(package, name))


def load_geojson(package: str, name: str) -> dict:
    data = load_json(package, name)
    kind = data.get("type") if isinstance(data, dict) else None
    if kind not in ("Feature", "FeatureCollection"):
        raise AssertionError(
            f"{package}/{name} is not GeoJSON: type is {kind!r}, "
            "expected 'Feature' or 'FeatureCollection'"
        )
    return data


def copy_fixture_tree(package: str, name: str, dest: Path) -> Path:
    """Copy a fixture directory into ``dest`` and return the new path."""
    src = fixture_path(package, name)
    if not src.is_dir():
        raise NotADirectoryError(f"fixture is not a directory: {src}")
    target = dest / src.name
    shutil.copytree(src, target)
    return target
