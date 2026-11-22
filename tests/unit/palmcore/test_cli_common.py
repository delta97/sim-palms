from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from palmcore.cli_common import (
    add_common_args,
    add_region_arg,
    build_context,
    build_paths,
    run_main,
)
from palmcore.context import RunContext
from palmcore.errors import CacheMiss, ConfigError, ContractError, SourceError
from palmcore.log import LOGGER_ROOT
from tests.helpers.fixtures import fixture_path


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


def _ok(_args: argparse.Namespace) -> int:
    return 0


def _parser(func: Callable[[argparse.Namespace], int] = _ok) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="t")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("go")
    add_common_args(p)
    add_region_arg(p, required=False)
    p.set_defaults(func=func)
    return parser


def _raiser(exc: BaseException) -> Callable[[argparse.Namespace], int]:
    def func(_args: argparse.Namespace) -> int:
        raise exc

    return func


def test_flags_beat_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PALMFIX_BUILD_DIR", str(tmp_path / "env-build"))
    monkeypatch.setenv("PALMFIX_DATA_DIR", str(tmp_path / "env-data"))

    args = _parser().parse_args(["go", "--build-dir", str(tmp_path / "flag-build")])
    paths = build_paths(args)
    assert paths.build_dir == (tmp_path / "flag-build").resolve()
    assert paths.data_dir == (tmp_path / "env-data").resolve()


def test_verbose_and_quiet_are_exclusive(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_main(_parser(), ["go", "-v", "-q"]) == 2
    assert "not allowed with" in capsys.readouterr().err


def test_no_subcommand_prints_help_and_returns_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_main(_parser(), []) == 2
    assert "usage:" in capsys.readouterr().out


def test_success_returns_function_result() -> None:
    assert run_main(_parser(), ["go"]) == 0


@pytest.mark.parametrize(
    ("exc", "code"),
    [
        (ConfigError("bad config"), 2),
        (ContractError("bad contract"), 3),
        (CacheMiss("no cache"), 5),
        (KeyboardInterrupt(), 130),
        (RuntimeError("boom"), 1),
    ],
)
def test_exceptions_map_to_exit_codes(exc: BaseException, code: int) -> None:
    assert run_main(_parser(_raiser(exc)), ["go"]) == code


def test_unexpected_error_logs_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    assert run_main(_parser(_raiser(RuntimeError("boom"))), ["go"]) == 1
    err = capsys.readouterr().err
    assert "boom" in err
    assert "Traceback" in err


def test_error_map_overrides_default() -> None:
    parser = _parser(_raiser(ContractError("bad")))
    assert run_main(parser, ["go"], error_map={ContractError: 7}) == 7


def test_error_map_most_specific_class_wins() -> None:
    parser = _parser(_raiser(CacheMiss("no cache")))
    assert run_main(parser, ["go"], error_map={SourceError: 8, CacheMiss: 9}) == 9
    assert run_main(parser, ["go"], error_map={SourceError: 8}) == 8


def test_error_map_covers_non_palmfix_errors() -> None:
    parser = _parser(_raiser(ValueError("x")))
    assert run_main(parser, ["go"], error_map={ValueError: 4}) == 4


def test_log_file_created_under_build_logs(tmp_path: Path) -> None:
    args = _parser().parse_args(["go", "--build-dir", str(tmp_path)])
    ctx = build_context(args, "palmfix")
    ctx.log.info("hello")
    assert ctx.log_file is not None
    assert ctx.log_file.parent == (tmp_path / "logs").resolve()
    assert ctx.log_file.name.startswith("palmfix-")
    assert "hello" in ctx.log_file.read_text(encoding="utf-8")


def test_no_log_file(tmp_path: Path) -> None:
    args = _parser().parse_args(["go", "--build-dir", str(tmp_path), "--no-log-file"])
    ctx = build_context(args, "palmfix")
    assert ctx.log_file is None
    assert not (tmp_path / "logs").exists()


def test_explicit_log_file(tmp_path: Path) -> None:
    target = tmp_path / "custom" / "run.log"
    argv = ["go", "--build-dir", str(tmp_path), "--log-file", str(target)]
    ctx = build_context(_parser().parse_args(argv), "palmfix")
    ctx.log.warning("x")
    assert ctx.log_file == target
    assert target.is_file()


def test_build_context_loads_region(tmp_path: Path) -> None:
    regions = fixture_path("palmcore", "regions")
    argv = [
        "go",
        "--build-dir",
        str(tmp_path),
        "--no-log-file",
        "--regions-dir",
        str(regions),
        "--region",
        "minimal",
    ]
    args = _parser().parse_args(argv)
    assert build_context(args, "palmfix").require_region().region == "minimal"
    assert build_context(args, "palmfix", load_region_arg=False).region is None


def test_require_region_raises_when_none(tmp_path: Path) -> None:
    args = _parser().parse_args(["go", "--build-dir", str(tmp_path), "--no-log-file"])
    ctx = build_context(args, "palmfix")
    assert isinstance(ctx, RunContext)
    assert ctx.region is None
    with pytest.raises(ConfigError):
        ctx.require_region()
