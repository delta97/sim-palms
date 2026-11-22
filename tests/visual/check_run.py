"""Check one in-sim visual run and optionally record pass or fail in the test log (TEST-102).

Plan: plans/detailed/06-testing.md#visual-protocol, step 7.

    python -m tests.visual.check_run tests/visual/T1/2026-11-22_phase2
    python -m tests.visual.check_run tests/visual/T1/2026-11-22_phase2 --update-log

Checks:
  - run.yaml has every required key; tester, sim_version and sdk_version are not still VERIFY;
  - every variant in run.yaml has VP1_street.jpg, VP2_oblique.jpg and VP3_approach.jpg;
  - checklist.md has rows C1 to C8, and each VP1/VP2/VP3 cell is pass, fail or na (no blanks).

Result: pass when there are no problems and no fail cell. fail when any cell is fail.
Otherwise the run is incomplete: problems are listed and the Result cell stays pending.
With --update-log the Result cell of the matching row becomes pass or fail (never for an
incomplete run without a fail cell).

Exit codes: 0 pass, 1 fail or incomplete, 2 bad input (missing folder, run.yaml or log row).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final

from palmcore.errors import EXIT_OK, EXIT_UNEXPECTED, PalmfixError
from palmcore.log import get_logger
from tests.helpers.fixtures import REPO_ROOT
from tests.visual.new_run import (
    CHECKLIST,
    REQUIRED_RUN_KEYS,
    UNSET,
    VIEWPOINT_FILES,
    VisualRunError,
    load_run,
    parse_variants,
    set_log_result,
    split_row,
)

logger = get_logger(__name__)

CHECK_IDS: Final = tuple(f"C{i}" for i in range(1, 9))
VP_COLUMNS: Final = ("VP1", "VP2", "VP3")
CELL_VALUES: Final = ("pass", "fail", "na")
CHECKLIST_HEADER: Final = ("Id", "Check", *VP_COLUMNS)
UNSET_KEYS: Final = ("tester", "sim_version", "sdk_version")


def parse_checklist(text: str) -> dict[str, dict[str, str]]:
    """Return ``{check_id: {vp: cell}}`` for the table in checklist.md.

    Raises VisualRunError if the table header is missing. Missing check rows are reported by
    :func:`checklist_problems`, not here.
    """
    lines = text.split("\n")
    header = next(
        (
            i
            for i, line in enumerate(lines)
            if line.lstrip().startswith("|")
            and split_row(line)[: len(CHECKLIST_HEADER)] == list(CHECKLIST_HEADER)
        ),
        None,
    )
    if header is None:
        raise VisualRunError(
            "checklist.md: table header '| Id | Check | VP1 | VP2 | VP3 |' not found"
        )
    cells: dict[str, dict[str, str]] = {}
    for line in lines[header + 2 :]:
        if not line.lstrip().startswith("|"):
            break
        row = split_row(line)
        if len(row) < len(CHECKLIST_HEADER):
            continue
        cells[row[0]] = dict(zip(VP_COLUMNS, row[2:5], strict=True))
    return cells


def checklist_problems(cells: dict[str, dict[str, str]]) -> tuple[list[str], list[str]]:
    """Return ``(problems, fails)``. Problems are blanks, invalid values and missing rows."""
    problems: list[str] = []
    fails: list[str] = []
    for check in CHECK_IDS:
        if check not in cells:
            problems.append(f"checklist.md: row {check} is missing")
            continue
        for vp in VP_COLUMNS:
            value = cells[check].get(vp, "")
            if value == "":
                problems.append(f"checklist.md: {check} {vp} is blank")
            elif value not in CELL_VALUES:
                problems.append(f"checklist.md: {check} {vp} is '{value}'; use pass, fail or na")
            elif value == "fail":
                fails.append(f"{check} at {vp} is fail")
    return problems, fails


def run_problems(run: dict[str, Any]) -> list[str]:
    """Problems with run.yaml itself (missing keys, unset values, bad variants or packages)."""
    problems = [f"run.yaml: missing key {key}" for key in REQUIRED_RUN_KEYS if key not in run]
    for key in UNSET_KEYS:
        if str(run.get(key, "")).strip() in ("", UNSET):
            problems.append(f"run.yaml: {key} is still {UNSET}; fill it in")
    packages = run.get("packages")
    if not isinstance(packages, dict) or not packages.get("region"):
        problems.append("run.yaml: packages.region is missing")
    if not isinstance(run.get("deviations"), list):
        problems.append("run.yaml: deviations must be a list (use [] for none)")
    return problems


def image_problems(run_dir: Path, variants: Sequence[str]) -> list[str]:
    problems = []
    for variant in variants:
        for name in VIEWPOINT_FILES:
            if not (run_dir / variant / name).is_file():
                problems.append(f"missing image {variant}/{name}")
    return problems


def check_run(run_dir: Path) -> tuple[str, list[str]]:
    """Return ``(result, problems)`` where result is ``pass``, ``fail`` or ``incomplete``.

    Raises VisualRunError when the folder, run.yaml or checklist.md cannot be read at all.
    """
    if not run_dir.is_dir():
        raise VisualRunError(f"{run_dir}: run folder not found")
    run = load_run(run_dir)
    problems = run_problems(run)
    raw_variants = run.get("variants")
    variants: tuple[str, ...] = ()
    if isinstance(raw_variants, list) and raw_variants:
        try:
            variants = parse_variants(",".join(str(v) for v in raw_variants))
        except VisualRunError as exc:
            problems.append(f"run.yaml: {exc}")
    else:
        problems.append("run.yaml: variants must be a non-empty list")

    problems += image_problems(run_dir, variants)

    checklist_path = run_dir / CHECKLIST
    if not checklist_path.is_file():
        raise VisualRunError(f"{checklist_path}: checklist not found")
    cells = parse_checklist(checklist_path.read_text(encoding="utf-8"))
    cell_problems, fails = checklist_problems(cells)
    problems += cell_problems

    if fails:
        return "fail", problems + [f"fail cell: {f}" for f in fails]
    if problems:
        return "incomplete", problems
    return "pass", []


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.visual.check_run",
        description=(
            "Check a visual run folder: run.yaml keys, the VP images for each variant, and "
            "every checklist cell. --update-log writes pass or fail to tests/visual/test_log.md."
        ),
    )
    parser.add_argument("run_dir", type=Path, metavar="RUN_DIR")
    parser.add_argument(
        "--update-log",
        action="store_true",
        help="set the Result cell of this run's row (pass, or fail if a cell failed)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT,
        metavar="DIR",
        help="repo root holding tests/visual (default: this repo; tests use a temp dir)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    run_dir: Path = args.run_dir
    try:
        result, problems = check_run(run_dir)
        if result == "pass":
            print(f"PASS {run_dir}")
        else:
            label = "FAIL" if result == "fail" else "INCOMPLETE"
            print(f"{label} {run_dir}")
            for problem in problems:
                print(f"  - {problem}")

        if args.update_log:
            folder = f"{run_dir.parent.name}/{run_dir.name}"
            if result == "incomplete":
                print("Result left pending: the run is incomplete, not failed")
            else:
                set_log_result(args.root, folder, "pass" if result == "pass" else "fail")
                print(f"test log: {folder} Result = {'pass' if result == 'pass' else 'fail'}")
        return EXIT_OK if result == "pass" else EXIT_UNEXPECTED
    except PalmfixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
