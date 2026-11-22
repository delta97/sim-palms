"""Add a row to the regression log, or set one check cell in an existing row.

Plan: plans/detailed/06-testing.md#regression and #regression-log-format.

    python -m tests.regression.new_entry --trigger SU --sim-version 1.9.24.0 --sdk-version 1.8.2
    python -m tests.regression.new_entry set 2026-11-22 R1 pass [--trigger SU]

The add form appends one row with every check cell ``pending`` and a Notes link to
``tests/regression/runs/<date>/notes.md``, creating that file from a template if it is missing.
It refuses a second row for the same date and trigger. The set form changes exactly one cell.

Exit codes follow palmcore: 0 ok, 2 bad input or refusal (also argparse errors).
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from palmcore.errors import EXIT_OK, ConfigError, PalmfixError
from palmcore.log import get_logger
from tests.helpers.fixtures import REPO_ROOT

logger = get_logger(__name__)

TRIGGERS: Final = ("SU", "hotfix", "beta", "SDK")
VALUES: Final = ("pass", "fail", "skip", "pending")

# Column headers exactly as in the plan's regression log format. Do not reorder.
COLUMNS: Final = (
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
# Check name used on the command line -> column header.
CHECK_COLUMNS: Final = {
    "R1": "R1 single blob",
    "R2": "R2 rebuild",
    "R3-T1": "R3 visual T1",
    "R3-T3": "R3 visual T3",
    "R4": "R4 full suite",
    "Result": "Result",
}
PENDING_CELLS: Final = ("pending", "pending", "pending", "pending", "pending", "pending")

LOG_RELPATH: Final = Path("tests") / "regression" / "LOG.md"
RUNS_RELDIR: Final = Path("tests") / "regression" / "runs"

NOTES_TEMPLATE: Final = """# Regression run {day} ({trigger})

- Sim version: {sim}
- SDK version: {sdk}
- Routine: tests/regression/ROUTINE.md. Log row: tests/regression/LOG.md ({day}, {trigger}).
- Installed versions: VERIFY on the user's PC if the values above were read from a source page.

Result cells: pass, fail, skip (say why), or pending. Never mark a check pass without evidence.

## R1 single blob

- Result: pending
- Evidence paths:
- Notes:

## R2 rebuild

- Result: pending
- Evidence paths: (build/palmfix-<region>/, build report, check_build output)
- Notes:

## R3 visual

- R3 visual T1 result: pending
- R3 visual T3 result: pending
- Evidence paths: (tests/visual/<run_dir>/, check_run output)
- Notes:

## R4 full suite

- Result: pending
- Evidence paths:
- Notes:

## Overall

- Result: pending
- Open items:
"""


class RegressionLogError(ConfigError):
    """The log is missing or malformed, a row would duplicate another, or an input is bad."""


def _date_arg(text: str) -> dt.date:
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"date must be YYYY-MM-DD, got {text!r}") from None


def _plain_arg(name: str, text: str) -> str:
    value = text.strip()
    if not value:
        raise RegressionLogError(f"{name} must not be empty")
    if "|" in value or "\n" in value or "\r" in value:
        raise RegressionLogError(f"{name} must not contain '|' or line breaks: {text!r}")
    return value


def log_path(root: Path) -> Path:
    return root / LOG_RELPATH


def run_dir(root: Path, day: dt.date) -> Path:
    return root / RUNS_RELDIR / day.isoformat()


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _format_row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _read_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise RegressionLogError(f"{path}: regression log not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise RegressionLogError(f"{path}: cannot read regression log: {exc}") from exc
    return text.split("\n")


def _header_index(lines: list[str], path: Path) -> int:
    for index, line in enumerate(lines):
        if line.lstrip().startswith("|") and _split_row(line) == list(COLUMNS):
            if index + 1 >= len(lines) or not lines[index + 1].lstrip().startswith("|---"):
                raise RegressionLogError(f"{path}: table separator missing under the header")
            return index
    raise RegressionLogError(
        f"{path}: table header does not match the plan's regression log format"
    )


def _table_rows(lines: list[str], header: int) -> list[int]:
    """Indexes of data rows under the header. The table ends at the first non-table line."""
    rows = []
    for index in range(header + 2, len(lines)):
        if not lines[index].lstrip().startswith("|"):
            break
        rows.append(index)
    return rows


def _matching_rows(lines: list[str], header: int, day: dt.date, trigger: str | None) -> list[int]:
    found = []
    for index in _table_rows(lines, header):
        cells = _split_row(lines[index])
        if cells[0] == day.isoformat() and (trigger is None or cells[1] == trigger):
            found.append(index)
    return found


def _notes_text(day: dt.date, trigger: str, sim: str, sdk: str) -> str:
    return NOTES_TEMPLATE.format(day=day.isoformat(), trigger=trigger, sim=sim, sdk=sdk)


def add_entry(
    trigger: str,
    sim_version: str,
    sdk_version: str,
    *,
    day: dt.date,
    root: Path = REPO_ROOT,
) -> Path:
    """Append a pending row and create its notes file. Returns the notes path."""
    if trigger not in TRIGGERS:
        raise RegressionLogError(f"trigger must be one of {', '.join(TRIGGERS)}, got {trigger!r}")
    sim = _plain_arg("--sim-version", sim_version)
    sdk = _plain_arg("--sdk-version", sdk_version)

    path = log_path(root)
    lines = _read_lines(path)
    header = _header_index(lines, path)
    if _matching_rows(lines, header, day, trigger):
        raise RegressionLogError(
            f"{path}: a row for {day.isoformat()} {trigger} already exists; "
            "change its cells with the set subcommand instead"
        )

    notes = run_dir(root, day) / "notes.md"
    row = _format_row(
        [
            day.isoformat(),
            trigger,
            sim,
            sdk,
            *PENDING_CELLS,
            f"[notes](runs/{day.isoformat()}/notes.md)",
        ]
    )
    rows = _table_rows(lines, header)
    insert_at = (rows[-1] if rows else header + 1) + 1
    lines.insert(insert_at, row)

    if not notes.exists():
        notes.parent.mkdir(parents=True, exist_ok=True)
        notes.write_text(_notes_text(day, trigger, sim, sdk), encoding="utf-8", newline="\n")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    logger.info("added regression row %s %s to %s", day.isoformat(), trigger, path)
    return notes


def set_cell(
    day: dt.date,
    check: str,
    value: str,
    *,
    trigger: str | None = None,
    root: Path = REPO_ROOT,
) -> None:
    """Set one check cell in the row for ``day``; pass ``trigger`` if several rows share it."""
    if check not in CHECK_COLUMNS:
        raise RegressionLogError(f"check must be one of {', '.join(CHECK_COLUMNS)}, got {check!r}")
    if value not in VALUES:
        raise RegressionLogError(f"value must be one of {', '.join(VALUES)}, got {value!r}")
    if trigger is not None and trigger not in TRIGGERS:
        raise RegressionLogError(f"trigger must be one of {', '.join(TRIGGERS)}, got {trigger!r}")

    path = log_path(root)
    lines = _read_lines(path)
    header = _header_index(lines, path)
    matches = _matching_rows(lines, header, day, trigger)
    if not matches:
        what = f"{day.isoformat()} {trigger}" if trigger else day.isoformat()
        raise RegressionLogError(f"{path}: no row for {what}")
    if len(matches) > 1:
        raise RegressionLogError(
            f"{path}: {len(matches)} rows for {day.isoformat()}; pass --trigger to pick one"
        )

    index = matches[0]
    cells = _split_row(lines[index])
    cells[COLUMNS.index(CHECK_COLUMNS[check])] = value
    lines[index] = _format_row(cells)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    logger.info("set %s %s = %s in %s", day.isoformat(), check, value, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.regression.new_entry",
        description=(
            "Add a pending row to tests/regression/LOG.md and its notes file, "
            "or set one check cell (subcommand set)."
        ),
        epilog=(
            "examples:\n"
            "  python -m tests.regression.new_entry --trigger SU "
            "--sim-version 1.9.24.0 --sdk-version 1.8.2\n"
            "  python -m tests.regression.new_entry set 2026-11-22 R1 pass --trigger SU\n"
            "checks: " + ", ".join(CHECK_COLUMNS) + "; values: " + ", ".join(VALUES)
        ),
    )
    parser.add_argument("--trigger", choices=TRIGGERS, help="trigger that started the run")
    parser.add_argument("--sim-version", metavar="V", help="sim version as published or VERIFY")
    parser.add_argument("--sdk-version", metavar="V", help="SDK version as published or VERIFY")
    parser.add_argument(
        "--date", type=_date_arg, default=None, metavar="YYYY-MM-DD", help="default: today"
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        metavar="DIR",
        help="repo root holding tests/regression (default: this repo; tests use a temp dir)",
    )
    sub = parser.add_subparsers(dest="command", metavar="{set}")
    setp = sub.add_parser("set", help="set one check cell in an existing row")
    setp.add_argument("day", type=_date_arg, metavar="YYYY-MM-DD")
    setp.add_argument("check", choices=list(CHECK_COLUMNS), metavar="CHECK")
    setp.add_argument("value", choices=list(VALUES), metavar="VALUE")
    setp.add_argument("--trigger", choices=TRIGGERS, help="needed if the date has several rows")
    setp.add_argument("--root", type=Path, default=argparse.SUPPRESS, metavar="DIR")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    day = args.date or dt.date.today()
    root: Path = args.root
    try:
        if args.command == "set":
            set_cell(args.day, args.check, args.value, trigger=args.trigger, root=root)
            print(f"set {args.day.isoformat()} {args.check} = {args.value}")
            return EXIT_OK
        missing = [
            flag
            for flag, value in (
                ("--trigger", args.trigger),
                ("--sim-version", args.sim_version),
                ("--sdk-version", args.sdk_version),
            )
            if value is None
        ]
        if missing:
            parser.error(f"add mode needs {', '.join(missing)} (or use the set subcommand)")
        notes = add_entry(args.trigger, args.sim_version, args.sdk_version, day=day, root=root)
        print(f"added {day.isoformat()} {args.trigger} to {log_path(root)}")
        print(f"notes: {notes}")
        return EXIT_OK
    except PalmfixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
