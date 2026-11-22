"""palmscan.cli skeleton."""

from __future__ import annotations

from pathlib import Path

import pytest

from palmscan.cli import main


def test_help_lists_subcommands(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    for name in ("run", "priors", "eval"):
        assert name in out


def test_eval_missing_palms_file_exits_2(tmp_path: Path) -> None:
    argv = ["eval", "--palms", str(tmp_path / "p.geojson"), "--site", "T1", "--no-log-file"]
    assert main(argv) == 2


def test_bad_usage_exits_2() -> None:
    assert main(["run"]) == 2
    assert main(["run", "--region", "x", "--only", "bogus"]) == 2
    assert main([]) == 2
