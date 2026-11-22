from __future__ import annotations

from pathlib import Path

import pytest

from palmcore.errors import ConfigError
from palmcore.paths import Paths, ensure_dir


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = (tmp_path / "repo").resolve()
    (root / "sub" / "deeper").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "palmfix"\n', encoding="utf-8")
    return root


def test_defaults(repo: Path) -> None:
    p = Paths.resolve(cwd=repo / "sub" / "deeper", env={})
    assert p.repo_root == repo
    assert p.data_dir == repo / "data"
    assert p.build_dir == repo / "build"
    assert p.regions_dir == repo / "regions"
    assert not (repo / "data").exists()


def test_env_overrides_and_relative_resolution(repo: Path, tmp_path: Path) -> None:
    other = (tmp_path / "elsewhere").resolve()
    env = {
        "PALMFIX_DATA_DIR": str(other),
        "PALMFIX_BUILD_DIR": "out/b",
        "PALMFIX_REGIONS_DIR": "cfg",
    }
    p = Paths.resolve(cwd=repo / "sub", env=env)
    assert p.data_dir == other
    assert p.build_dir == repo / "out" / "b"
    assert p.regions_dir == repo / "cfg"


def test_env_root(repo: Path, tmp_path: Path) -> None:
    other = (tmp_path / "alt").resolve()
    p = Paths.resolve(cwd=repo, env={"PALMFIX_ROOT": str(other)})
    assert p.repo_root == other
    assert p.data_dir == other / "data"


def test_explicit_beats_env(repo: Path, tmp_path: Path) -> None:
    explicit = (tmp_path / "flag").resolve()
    p = Paths.resolve(
        data_dir=explicit, cwd=repo, env={"PALMFIX_DATA_DIR": str(tmp_path / "envdir")}
    )
    assert p.data_dir == explicit
    rel = Paths.resolve(build_dir=Path("rel"), cwd=repo, env={})
    assert rel.build_dir == repo / "rel"


def test_region_paths(repo: Path) -> None:
    p = Paths.resolve(cwd=repo, env={})
    assert p.palms_path("san-diego-coastal").parts[-4:] == (
        "build",
        "scan",
        "san-diego-coastal",
        "palms.geojson",
    )
    assert p.package_project_dir("san-diego-coastal").name == "palmfix-san-diego-coastal"
    assert p.package_project_dir("san-diego-coastal").parent == repo / "build"
    assert p.region_file("san-diego-coastal") == repo / "regions" / "san-diego-coastal.yaml"
    assert p.logs_dir() == repo / "build" / "logs"


@pytest.mark.parametrize("bad", ["../x", "A", "a/b", "a--b", "", "-a", "a\\b"])
def test_bad_region(repo: Path, bad: str) -> None:
    p = Paths.resolve(cwd=repo, env={})
    with pytest.raises(ConfigError):
        p.region_file(bad)
    with pytest.raises(ConfigError):
        p.palms_path(bad)


def test_ensure_dir(tmp_path: Path) -> None:
    target = tmp_path / "a" / "b"
    assert ensure_dir(target) == target
    assert target.is_dir()
    assert ensure_dir(target) == target
