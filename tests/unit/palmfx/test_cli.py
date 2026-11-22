"""palmfx.offline.cli: discovery of command modules and the shared runner."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from palmcore.errors import ConfigError
from palmfx.offline import cli
from palmfx.offline.session import new_session


def _run(args: argparse.Namespace) -> int:
    session = cli.session_from_args(args)
    return int(session.meta.get("exit", 0))


def _module(name: str, *, with_register: bool = True) -> ModuleType:
    mod = ModuleType(f"palmfx.offline.commands.{name}")
    if with_register:

        def register(sub: Any) -> None:
            p = sub.add_parser(name, help="dummy")
            cli.add_standard_args(p)
            p.set_defaults(func=_run)

        mod.register = register  # type: ignore[attr-defined]
    return mod


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--help"]) == 0
    assert "palmfx" in capsys.readouterr().out


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.startswith("palmfx ")


def test_no_command_is_usage_error() -> None:
    assert cli.main([]) == 2


def test_registered_command_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "discover_commands", lambda: [_module("dummy")])
    new_session(tmp_path / "s", {"exit": 0})
    assert cli.main(["dummy", "--session", str(tmp_path / "s"), "--no-log-file"]) == 0
    assert cli.main(["--help"]) == 0
    assert "dummy" in capsys.readouterr().out


def test_command_exit_code_is_returned(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "discover_commands", lambda: [_module("dummy")])
    new_session(tmp_path / "s", {"exit": 4})
    assert cli.main(["dummy", "--session", str(tmp_path / "s"), "--no-log-file"]) == 4


def test_missing_session_maps_to_config_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "discover_commands", lambda: [_module("dummy")])
    argv = ["dummy", "--session", str(tmp_path / "nope"), "--no-log-file"]
    assert cli.main(argv) == ConfigError.exit_code


def test_session_flag_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "discover_commands", lambda: [_module("dummy")])
    assert cli.main(["dummy"]) == 2


def test_module_without_register_is_skipped(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        cli, "discover_commands", lambda: [_module("bare", with_register=False), _module("ok")]
    )
    with caplog.at_level("WARNING"):
        parser = cli.build_parser()
    assert "has no register" in caplog.text
    listing = parser.format_help().split("COMMAND", 2)[-1]
    assert "ok" in listing
    assert "bare" not in listing


def test_discovery_finds_new_module_without_editing_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    pkg = tmp_path / "fakecmds"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "hello.py").write_text(
        "def register(sub):\n"
        "    p = sub.add_parser('hello')\n"
        "    p.set_defaults(func=lambda a: 0)\n",
        encoding="utf-8",
    )
    (pkg / "broken.py").write_text("import not_a_real_module_xyz\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    fake = ModuleType("fakecmds")
    fake.__path__ = [str(pkg)]
    monkeypatch.setattr(cli, "commands", fake)
    with caplog.at_level("WARNING"):
        found = [m.__name__ for m in cli.discover_commands()]
    assert found == ["fakecmds.hello"]
    assert "skipping command module fakecmds.broken" in caplog.text
    assert cli.main(["hello"]) == 0


def test_shipped_commands_package_imports_cleanly() -> None:
    assert isinstance(cli.discover_commands(), list)


def test_python_dash_m_help() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "palmfx.offline", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "palmfx" in proc.stdout
