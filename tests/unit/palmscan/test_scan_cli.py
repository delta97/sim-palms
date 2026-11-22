"""palmscan.cli skeleton."""

from __future__ import annotations

import pytest

from palmscan.cli import main


def test_help_lists_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    for name in ("run", "priors", "eval"):
        assert name in out


@pytest.mark.parametrize(
    "argv",
    [
        ["run", "--region", "san-diego-coastal", "--offline", "--only", "inventory", "-vv"],
        ["priors", "--region", "san-diego-coastal", "--offline"],
        ["eval", "--palms", "p.geojson", "--site", "t1"],
    ],
)
def test_handlers_not_implemented_exit_1(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 1
    assert "not implemented" in capsys.readouterr().err


def test_bad_usage_exits_2() -> None:
    assert main(["run"]) == 2
    assert main(["run", "--region", "x", "--only", "bogus"]) == 2
    assert main([]) == 2
