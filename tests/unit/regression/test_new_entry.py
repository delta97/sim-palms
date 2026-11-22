"""Self-tests for tests/regression/new_entry.py, run against a temp copy of the repo layout."""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pytest

from tests.helpers.fixtures import REPO_ROOT
from tests.regression.new_entry import (
    COLUMNS,
    LOG_RELPATH,
    RegressionLogError,
    _header_index,
    _read_lines,
    _split_row,
    add_entry,
    main,
    set_cell,
)

DAY = dt.date(2026, 11, 22)
COMMITTED_LOG = REPO_ROOT / LOG_RELPATH


@pytest.fixture
def root(tmp_path: Path) -> Path:
    dest = tmp_path / LOG_RELPATH
    dest.parent.mkdir(parents=True)
    shutil.copy(COMMITTED_LOG, dest)
    return tmp_path


def _log(root: Path) -> list[str]:
    return (root / LOG_RELPATH).read_text(encoding="utf-8").split("\n")


def _rows(root: Path) -> list[list[str]]:
    lines = _log(root)
    header = _header_index(lines, root / LOG_RELPATH)
    out = []
    for line in lines[header + 2 :]:
        if not line.lstrip().startswith("|"):
            break
        out.append(_split_row(line))
    return out


def test_committed_header_matches_plan() -> None:
    lines = _read_lines(COMMITTED_LOG)
    assert _split_row(lines[_header_index(lines, COMMITTED_LOG)]) == list(COLUMNS)
    assert COLUMNS == (
        "Date",
        "Trigger",
        "Sim version",
        "SDK version",
        "R1 single blob",
        "R2 rebuild",
        "R3 visual T1",
        "R3 visual T3",
        "R4 full suite",
        "Result",
        "Notes",
    )


def test_add_appends_pending_row_with_matching_width(root: Path) -> None:
    notes = add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    rows = _rows(root)
    assert len(rows) == 1
    row = rows[0]
    assert len(row) == len(COLUMNS)
    assert row[:4] == ["2026-11-22", "SU", "1.9.24.0", "1.8.2"]
    assert row[4:10] == ["pending"] * 6
    assert row[10] == "[notes](runs/2026-11-22/notes.md)"
    assert notes == root / "tests" / "regression" / "runs" / "2026-11-22" / "notes.md"
    assert notes.exists()


def test_add_keeps_text_outside_the_table(root: Path) -> None:
    before = _log(root)
    add_entry("beta", "1.9.25.0", "VERIFY", day=DAY, root=root)
    after = _log(root)
    new = [line for line in after if line not in before]
    assert len(new) == 1
    assert new[0].startswith("| 2026-11-22 | beta |")
    assert [line for line in after if line != new[0]] == before


def test_rows_stay_in_date_order_on_append(root: Path) -> None:
    add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    add_entry("hotfix", "1.9.24.1", "1.8.2", day=DAY + dt.timedelta(days=1), root=root)
    assert [r[0] for r in _rows(root)] == ["2026-11-22", "2026-11-23"]
    assert _log(root)[-1] == ""


def test_notes_file_has_result_headings(root: Path) -> None:
    notes = add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    text = notes.read_text(encoding="utf-8")
    for heading in ("## R1 single blob", "## R2 rebuild", "## R3 visual", "## R4 full suite"):
        assert heading in text
    assert "VERIFY on the user's PC" in text


def test_existing_notes_file_is_not_overwritten(root: Path) -> None:
    notes = root / "tests" / "regression" / "runs" / "2026-11-22" / "notes.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("keep me\n", encoding="utf-8")
    add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    assert notes.read_text(encoding="utf-8") == "keep me\n"


def test_duplicate_date_and_trigger_is_refused(root: Path) -> None:
    add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    before = _log(root)
    with pytest.raises(RegressionLogError, match="already exists"):
        add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    assert _log(root) == before


def test_same_date_different_trigger_is_allowed(root: Path) -> None:
    add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    add_entry("SDK", "1.9.24.0", "1.8.3", day=DAY, root=root)
    assert [r[1] for r in _rows(root)] == ["SU", "SDK"]


def test_set_changes_only_the_target_cell(root: Path) -> None:
    add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    before = _rows(root)[0]
    set_cell(DAY, "R3-T3", "fail", trigger="SU", root=root)
    after = _rows(root)[0]
    changed = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    assert changed == [COLUMNS.index("R3 visual T3")]
    assert after[7] == "fail"


def test_set_maps_each_check_to_its_column(root: Path) -> None:
    add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    for check, column, value in (
        ("R1", "R1 single blob", "pass"),
        ("R2", "R2 rebuild", "skip"),
        ("R3-T1", "R3 visual T1", "fail"),
        ("R4", "R4 full suite", "pass"),
        ("Result", "Result", "fail"),
    ):
        set_cell(DAY, check, value, root=root)
        assert _rows(root)[0][COLUMNS.index(column)] == value


def test_set_without_trigger_needs_unique_row(root: Path) -> None:
    add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    add_entry("SDK", "1.9.24.0", "1.8.3", day=DAY, root=root)
    with pytest.raises(RegressionLogError, match="pass --trigger"):
        set_cell(DAY, "R1", "pass", root=root)
    set_cell(DAY, "R1", "pass", trigger="SDK", root=root)
    assert [r[4] for r in _rows(root)] == ["pending", "pass"]


def test_set_on_missing_row_is_refused(root: Path) -> None:
    with pytest.raises(RegressionLogError, match="no row"):
        set_cell(DAY, "R1", "pass", root=root)


@pytest.mark.parametrize("value", ["PASS", "ok", "", "done"])
def test_set_rejects_invalid_value(root: Path, value: str) -> None:
    add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    before = _log(root)
    with pytest.raises(RegressionLogError, match="value must be one of"):
        set_cell(DAY, "R1", value, root=root)
    assert _log(root) == before


def test_set_rejects_unknown_check(root: Path) -> None:
    add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=root)
    with pytest.raises(RegressionLogError, match="check must be one of"):
        set_cell(DAY, "R5", "pass", root=root)


def test_add_rejects_unknown_trigger(root: Path) -> None:
    with pytest.raises(RegressionLogError, match="trigger must be one of"):
        add_entry("patch", "1.9.24.0", "1.8.2", day=DAY, root=root)


def test_add_rejects_pipe_in_version(root: Path) -> None:
    with pytest.raises(RegressionLogError, match="must not contain"):
        add_entry("SU", "1.9|24", "1.8.2", day=DAY, root=root)


def test_missing_header_is_refused(tmp_path: Path) -> None:
    dest = tmp_path / LOG_RELPATH
    dest.parent.mkdir(parents=True)
    dest.write_text("# Regression log\n\n| Date | Trigger |\n|---|---|\n", encoding="utf-8")
    with pytest.raises(RegressionLogError, match="does not match"):
        add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=tmp_path)


def test_missing_log_is_refused(tmp_path: Path) -> None:
    with pytest.raises(RegressionLogError, match="not found"):
        add_entry("SU", "1.9.24.0", "1.8.2", day=DAY, root=tmp_path)


def test_cli_add_and_set(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(
        [
            "--root",
            str(root),
            "--trigger",
            "SU",
            "--sim-version",
            "1.9.24.0",
            "--sdk-version",
            "1.8.2",
            "--date",
            "2026-11-22",
        ]
    )
    assert code == 0
    assert "added 2026-11-22 SU" in capsys.readouterr().out
    code = main(["--root", str(root), "set", "2026-11-22", "R2", "fail", "--trigger", "SU"])
    assert code == 0
    assert _rows(root)[0][COLUMNS.index("R2 rebuild")] == "fail"


def test_cli_refused_duplicate_exits_2(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = ["--root", str(root), "--trigger", "SU", "--sim-version", "1", "--sdk-version", "2"]
    args += ["--date", "2026-11-22"]
    assert main(args) == 0
    assert main(args) == 2
    assert "already exists" in capsys.readouterr().err


def test_cli_add_mode_needs_versions(root: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(root), "--trigger", "SU"])
    assert exc.value.code == 2


def test_cli_bad_date_is_argparse_error(root: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--root", str(root), "set", "22-11-2026", "R1", "pass"])
    assert exc.value.code == 2


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "--trigger" in capsys.readouterr().out
