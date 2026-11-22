"""Where data/, build/ and regions/ live, with flag and environment overrides."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from palmcore.errors import ConfigError

REGION_RE: Final = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

_ROOT_MARKER: Final = 'name = "palmfix"'


def _is_repo_root(directory: Path) -> bool:
    try:
        text = (directory / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return False
    return any(line.strip() == _ROOT_MARKER for line in text.splitlines())


def _find_repo_root(cwd: Path) -> Path:
    start = cwd.resolve()
    for candidate in (start, *start.parents):
        if _is_repo_root(candidate):
            return candidate
    return Path(__file__).resolve().parents[1]


def _absolute(value: Path | str, base: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def _check_region(region: str) -> str:
    if not REGION_RE.match(region):
        raise ConfigError(f"invalid region name {region!r}: use lowercase letters, digits and '-'")
    return region


@dataclass(frozen=True)
class Paths:
    """Resolved project directories. Creates nothing; use :func:`ensure_dir`."""

    repo_root: Path
    data_dir: Path
    build_dir: Path
    regions_dir: Path

    @classmethod
    def resolve(
        cls,
        *,
        repo_root: Path | None = None,
        data_dir: Path | None = None,
        build_dir: Path | None = None,
        regions_dir: Path | None = None,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
    ) -> Paths:
        """Resolve directories: explicit argument > environment variable > default."""
        environ: Mapping[str, str] = os.environ if env is None else env
        start = Path.cwd() if cwd is None else cwd

        if repo_root is not None:
            root = _absolute(repo_root, start)
        elif environ.get("PALMFIX_ROOT"):
            root = _absolute(environ["PALMFIX_ROOT"], start)
        else:
            root = _find_repo_root(start)

        def pick(explicit: Path | None, var: str, default: str) -> Path:
            if explicit is not None:
                return _absolute(explicit, root)
            if environ.get(var):
                return _absolute(environ[var], root)
            return root / default

        return cls(
            repo_root=root,
            data_dir=pick(data_dir, "PALMFIX_DATA_DIR", "data"),
            build_dir=pick(build_dir, "PALMFIX_BUILD_DIR", "build"),
            regions_dir=pick(regions_dir, "PALMFIX_REGIONS_DIR", "regions"),
        )

    def region_file(self, region: str) -> Path:
        return self.regions_dir / f"{_check_region(region)}.yaml"

    def scan_out_dir(self, region: str) -> Path:
        return self.build_dir / "scan" / _check_region(region)

    def palms_path(self, region: str) -> Path:
        return self.scan_out_dir(region) / "palms.geojson"

    def package_project_dir(self, region: str) -> Path:
        return self.build_dir / f"palmfix-{_check_region(region)}"

    def logs_dir(self) -> Path:
        return self.build_dir / "logs"


def ensure_dir(path: Path) -> Path:
    """Create ``path`` (and parents) if missing and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path
