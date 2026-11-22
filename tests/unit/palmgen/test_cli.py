import argparse
import subprocess
import sys
import types
from pathlib import Path

import pytest

from palmgen import __version__, cli
from palmgen.errors import (
    CompileError,
    GenerationError,
    InputError,
    OutputCheckError,
    PalmgenError,
    SimRunningError,
    ToolUnavailableError,
)

BUILD_FLAGS = [
    "--region", "--config", "--palms", "--buildings", "--manifest", "--models", "--placement",
    "--out", "--margin-m", "--data-version", "--no-airport-mask", "--skip-compile",
    "--fspackagetool", "--allow-sim-running", "--allow-empty", "--timeout", "--verbose",
]  # fmt: skip
INDEX_FLAGS = [
    "--region", "--config", "--palms", "--manifest", "--out", "--data-version",
    "--allow-missing-titles",
]  # fmt: skip
AIRPORT_FLAGS = ["--region", "--config", "--out", "--endpoint"]


@pytest.mark.parametrize(
    ("argv", "flags"),
    [
        (["build"], BUILD_FLAGS),
        (["index"], INDEX_FLAGS),
        (["masks", "airports"], AIRPORT_FLAGS),
    ],
)
def test_help_lists_every_flag(
    argv: list[str], flags: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([*argv, "--help"]) == 0
    out = capsys.readouterr().out
    for flag in flags:
        assert flag in out


def test_version_in_module() -> None:
    assert __version__ == "0.1.0"


def test_exit_codes() -> None:
    codes = {
        PalmgenError: 1,
        InputError: 2,
        GenerationError: 3,
        CompileError: 4,
        OutputCheckError: 5,
        SimRunningError: 6,
        ToolUnavailableError: 7,
    }
    for cls, code in codes.items():
        assert cls.exit_code == code


def test_bad_placement_exits_2() -> None:
    assert cli.main(["build", "--region", "x", "--placement", "dynamic"]) == 2


def test_bad_models_exits_2() -> None:
    assert cli.main(["build", "--region", "x", "--models", "nope"]) == 2


@pytest.mark.parametrize("name", ["Bad Name", "UPPER", "a_b", "-a", "a-", "a--b", ""])
def test_bad_region_exits_2(name: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["build", f"--region={name}"]) == 2
    assert "invalid region name" in capsys.readouterr().err


def test_missing_region_exits_2() -> None:
    assert cli.main(["build"]) == 2


def test_missing_stage_returns_1(capsys: pytest.CaptureFixture[str]) -> None:
    # Stage modules do not exist in this task; later GEN tasks add them.
    import importlib.util

    if importlib.util.find_spec("palmgen.pipeline") is not None:
        pytest.skip("pipeline already implemented")
    assert cli.main(["build", "--region", "x"]) == 1
    assert "build is not implemented yet" in capsys.readouterr().err


def _stub(monkeypatch: pytest.MonkeyPatch, module: str, func: str, fn: object) -> None:
    mod = types.ModuleType(module)
    setattr(mod, func, fn)
    monkeypatch.setitem(sys.modules, module, mod)


def test_stubbed_stage_not_implemented(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def raiser(opts: argparse.Namespace) -> int:
        raise NotImplementedError("index is not implemented yet")

    _stub(monkeypatch, "palmgen.spatial_index", "run_index", raiser)
    assert cli.main(["index", "--region", "x"]) == 1
    assert capsys.readouterr().err == "error: index is not implemented yet\n"


def test_module_without_function_is_not_implemented(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setitem(sys.modules, "palmgen.masks", types.ModuleType("palmgen.masks"))
    assert cli.main(["masks", "airports", "--region", "x"]) == 1
    assert "masks airports is not implemented yet" in capsys.readouterr().err


def test_palmgen_error_maps_to_exit_code(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(opts: argparse.Namespace) -> int:
        raise CompileError("fspackagetool exited 1")

    _stub(monkeypatch, "palmgen.pipeline", "run_build", fail)
    assert cli.main(["build", "--region", "x"]) == 4
    assert capsys.readouterr().err == "error: fspackagetool exited 1\n"


def test_defaults_resolved_and_passed(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def ok(opts: argparse.Namespace) -> int:
        seen["opts"] = opts
        return 0

    _stub(monkeypatch, "palmgen.pipeline", "run_build", ok)
    assert cli.main(["build", "--region", "san-diego"]) == 0
    o = seen["opts"]
    assert o.config == Path("regions/san-diego.yaml")
    assert o.palms == Path("build/scan/san-diego/palms.geojson")
    assert o.buildings == Path("build/scan/san-diego/buildings.geojson")
    assert o.manifest == Path("assets/manifest.json")
    assert (o.models, o.placement, o.out, o.timeout) == ("library", "static", Path("build"), 3600)
    assert o.margin_m is None
    assert not o.skip_compile


def test_airports_default_out(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, argparse.Namespace] = {}

    def ok(opts: argparse.Namespace) -> int:
        seen["opts"] = opts
        return 0

    _stub(monkeypatch, "palmgen.masks", "run_fetch_airports", ok)
    assert cli.main(["masks", "airports", "--region", "x"]) == 0
    assert seen["opts"].out == Path("data/x/masks/airports.geojson")
    assert seen["opts"].endpoint == "https://overpass-api.de/api/interpreter"


def test_python_dash_m_and_light_imports() -> None:
    code = (
        "import sys, palmgen.cli;assert not {'shapely','lxml'} & set(sys.modules), 'heavy import'"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
    proc = subprocess.run(
        [sys.executable, "-m", "palmgen", "build", "--region", "Bad Name"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 2
