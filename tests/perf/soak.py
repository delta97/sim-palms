"""Soak-test report for the live spawner (TEST-014): check a telemetry log, write Markdown.

Plan: plans/detailed/06-testing.md#soak-test and #soak-telemetry-format.

    python -m tests.perf.soak <telemetry.jsonl> [--config <yaml>] [--out <report.md>] [--no-audit]

Input is JSON Lines in the format the plan requests from LIVE (palmlive live spawner, LIVE-101).
Events used: `tick` (live, cap, spawned_total, removed_total, proc_private_mb), `shutdown_complete`
(live) and `audit` (palm_objects_found). Other events are ignored. Field meanings are fixed by the
plan; if palmlive writes a different shape, map it in `read_palmlive_log` and note the mapping in
tests/perf/SOAK.md. The audit method is VERIFY (V10): LIVE-101 confirms it on the sim PC.

Checks (limits from tests/perf/soak_config.yaml, all provisional):
  S1 live <= cap at every tick
  S2 last shutdown_complete.live == 0 and audit.palm_objects_found == 0
     (a missing audit fails unless --no-audit)
  S3 spawned_total - removed_total == live at every tick
  S4 least-squares slope of proc_private_mb over the last leak_window_min <= leak_mb_per_min_max
  S5 no gap between consecutive ticks longer than max_tick_gap_s
  S6 tick span >= min_duration_min

Exit codes: 0 all checks pass, 1 a check failed, 2 bad input (missing or unreadable file, bad
JSONL, missing fields, no tick events, non-increasing timestamps, bad config). The manual check S7
(forced kill, restart, cleanup) is not computed here; the run notes record it.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final

import numpy as np
import yaml

from palmcore.errors import EXIT_OK, ConfigError, PalmfixError
from palmcore.log import get_logger
from tests.helpers.fixtures import REPO_ROOT

logger = get_logger(__name__)

DEFAULT_CONFIG: Final = REPO_ROOT / "tests" / "perf" / "soak_config.yaml"

EXIT_CHECK_FAIL: Final = 1
EVENT_TICK: Final = "tick"
EVENT_SHUTDOWN_COMPLETE: Final = "shutdown_complete"
EVENT_AUDIT: Final = "audit"
REQUIRED_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    EVENT_TICK: ("live", "cap", "spawned_total", "removed_total", "proc_private_mb"),
    EVENT_SHUTDOWN_COMPLETE: ("live",),
    EVENT_AUDIT: ("palm_objects_found",),
}
COUNT_FIELDS: Final = frozenset(
    {"live", "cap", "spawned_total", "removed_total", "palm_objects_found"}
)


class SoakInputError(ConfigError):
    """The telemetry log or the soak config cannot be used. Exit code 2."""


# --- config -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class SoakConfig:
    provisional: bool
    leak_window_min: float
    leak_mb_per_min_max: float
    max_tick_gap_s: float
    min_duration_min: float


def _value(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise ConfigError(f"soak_config.yaml: {key} is missing")
    return data[key]


def _number(data: dict[str, Any], key: str, minimum: float | None = None) -> float:
    value = _value(data, key)
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ConfigError(f"soak_config.yaml: {key} must be a finite number, got {value!r}")
    if minimum is not None and value < minimum:
        raise ConfigError(f"soak_config.yaml: {key} must be >= {minimum}, got {value!r}")
    return float(value)


def load_config(path: Path | None = None) -> SoakConfig:
    """Load and validate soak_config.yaml. Every key is required; nothing is defaulted silently."""
    config_path = DEFAULT_CONFIG if path is None else path
    try:
        text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"{config_path}: soak config not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{config_path}: cannot read soak config: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{config_path}: top level must be a mapping")

    provisional = _value(data, "provisional")
    if not isinstance(provisional, bool):
        raise ConfigError("soak_config.yaml: provisional must be true or false")
    leak_window_min = _number(data, "leak_window_min", minimum=0)
    if leak_window_min <= 0:
        raise ConfigError("soak_config.yaml: leak_window_min must be > 0")
    return SoakConfig(
        provisional=provisional,
        leak_window_min=leak_window_min,
        leak_mb_per_min_max=_number(data, "leak_mb_per_min_max", minimum=0),
        max_tick_gap_s=_number(data, "max_tick_gap_s", minimum=0),
        min_duration_min=_number(data, "min_duration_min", minimum=0),
    )


# --- reading and parsing ----------------------------------------------------------------------


def read_palmlive_log(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL telemetry log into raw records (one dict per non-blank line).

    This is the adapter seam. It accepts the plan's format as written. If palmlive emits a
    different shape, map it here so the rest of the module sees the plan's field names.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SoakInputError(f"{path}: telemetry log not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise SoakInputError(f"{path}: cannot read telemetry log: {exc}") from exc

    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SoakInputError(f"{path}:{lineno}: invalid JSON: {exc.msg}") from None
        if not isinstance(record, dict):
            raise SoakInputError(f"{path}:{lineno}: each line must be a JSON object")
        if not isinstance(record.get("t"), str) or not isinstance(record.get("event"), str):
            raise SoakInputError(f"{path}:{lineno}: 't' and 'event' must be strings")
        records.append(record)
    return records


@dataclass(frozen=True)
class Tick:
    t: datetime
    live: int
    cap: int
    spawned_total: int
    removed_total: int
    proc_private_mb: float


@dataclass(frozen=True)
class Telemetry:
    ticks: list[Tick]
    shutdown_live: list[int]  # live count at each shutdown_complete, in file order
    audit_found: list[int]  # palm_objects_found at each audit, in file order
    n_records: int


def _parse_time(record: dict[str, Any], lineno: int) -> datetime:
    text: str = record["t"]
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        raise SoakInputError(f"record {lineno}: 't' is not an ISO 8601 time: {text!r}") from None
    if when.tzinfo is None:
        raise SoakInputError(f"record {lineno}: 't' needs a time zone (for example ...Z): {text!r}")
    return when


def _field(record: dict[str, Any], key: str, lineno: int) -> Any:
    if key not in record:
        raise SoakInputError(f"record {lineno} ({record['event']}): field '{key}' is missing")
    value = record[key]
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise SoakInputError(f"record {lineno}: '{key}' must be a finite number, got {value!r}")
    if key in COUNT_FIELDS and not isinstance(value, int):
        raise SoakInputError(f"record {lineno}: '{key}' must be an integer, got {value!r}")
    return value


def parse_telemetry(records: list[dict[str, Any]]) -> Telemetry:
    """Validate records and split them into ticks, shutdown and audit events.

    Unknown event names are ignored. Timestamps must not go backwards in file order.
    """
    ticks: list[Tick] = []
    shutdown_live: list[int] = []
    audit_found: list[int] = []
    previous: datetime | None = None
    for lineno, record in enumerate(records, start=1):
        when = _parse_time(record, lineno)
        if previous is not None and when < previous:
            raise SoakInputError(f"record {lineno}: time goes backwards ({record['t']})")
        previous = when
        event = record["event"]
        if event not in REQUIRED_FIELDS:
            continue
        values = {key: _field(record, key, lineno) for key in REQUIRED_FIELDS[event]}
        if event == EVENT_TICK:
            ticks.append(
                Tick(
                    t=when,
                    live=int(values["live"]),
                    cap=int(values["cap"]),
                    spawned_total=int(values["spawned_total"]),
                    removed_total=int(values["removed_total"]),
                    proc_private_mb=float(values["proc_private_mb"]),
                )
            )
        elif event == EVENT_SHUTDOWN_COMPLETE:
            shutdown_live.append(int(values["live"]))
        else:
            audit_found.append(int(values["palm_objects_found"]))
    if not ticks:
        raise SoakInputError("no 'tick' events in the telemetry log")
    return Telemetry(
        ticks=ticks, shutdown_live=shutdown_live, audit_found=audit_found, n_records=len(records)
    )


# --- checks -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    id: str
    name: str
    passed: bool
    measured: str
    limit: str
    note: str = ""


def check_s1_cap(ticks: list[Tick]) -> CheckResult:
    peak = max(ticks, key=lambda tick: tick.live)
    over = sum(1 for tick in ticks if tick.live > tick.cap)
    return CheckResult(
        id="S1",
        name="live <= cap at every tick",
        passed=over == 0,
        measured=f"max live {peak.live} (cap {peak.cap}); {over} tick(s) over cap",
        limit="live <= cap at every tick",
    )


def check_s2_shutdown(
    shutdown_live: list[int], audit_found: list[int], allow_no_audit: bool
) -> CheckResult:
    if not shutdown_live:
        return CheckResult(
            id="S2",
            name="zero after shutdown (live and audit)",
            passed=False,
            measured="no shutdown_complete event",
            limit="last shutdown_complete.live == 0 and audit.palm_objects_found == 0",
        )
    live_after = shutdown_live[-1]
    live_ok = live_after == 0
    if audit_found:
        found = audit_found[-1]
        measured = f"live after shutdown {live_after}; audit found {found}"
        passed = live_ok and found == 0
        note = ""
    elif allow_no_audit:
        measured = f"live after shutdown {live_after}; audit skipped"
        passed = live_ok
        note = "audit skipped (--no-audit)"
    else:
        measured = f"live after shutdown {live_after}; audit missing"
        passed = False
        note = "no audit event; rerun with --no-audit only if the audit was not done"
    return CheckResult(
        id="S2",
        name="zero after shutdown (live and audit)",
        passed=passed,
        measured=measured,
        limit="last shutdown_complete.live == 0 and audit.palm_objects_found == 0",
        note=note,
    )


def check_s3_bookkeeping(ticks: list[Tick]) -> CheckResult:
    bad = [tick for tick in ticks if tick.spawned_total - tick.removed_total != tick.live]
    first = f"; first at {bad[0].t.isoformat()}" if bad else ""
    return CheckResult(
        id="S3",
        name="spawned - removed == live at every tick",
        passed=not bad,
        measured=f"{len(bad)} of {len(ticks)} tick(s) mismatched{first}",
        limit="spawned_total - removed_total == live at every tick",
    )


def leak_slope(ticks: list[Tick], window_min: float) -> tuple[float, float, int]:
    """Least-squares slope (MB/min) of proc_private_mb over the last window_min minutes.

    Returns (slope, window span in minutes, number of ticks in the window).
    """
    last = ticks[-1].t
    window = [tick for tick in ticks if (last - tick.t).total_seconds() / 60.0 <= window_min]
    span_min = (window[-1].t - window[0].t).total_seconds() / 60.0
    x = np.array([(tick.t - window[0].t).total_seconds() / 60.0 for tick in window])
    y = np.array([tick.proc_private_mb for tick in window])
    slope = float(np.polyfit(x, y, 1)[0])
    return slope, span_min, len(window)


def check_s4_leak(ticks: list[Tick], config: SoakConfig) -> CheckResult:
    limit = (
        f"slope <= {config.leak_mb_per_min_max:g} MB/min "
        f"over the last {config.leak_window_min:g} min"
    )
    if len(ticks) < 2:
        return CheckResult("S4", "memory slope", False, "fewer than 2 ticks", limit)
    slope, span_min, n = leak_slope(ticks, config.leak_window_min)
    note = ""
    passed = slope <= config.leak_mb_per_min_max
    # The first tick in the window can sit up to one tick gap inside it, so allow that much.
    if span_min + config.max_tick_gap_s / 60.0 < config.leak_window_min:
        passed = False
        note = f"window spans {span_min:.1f} min, shorter than leak_window_min"
    return CheckResult(
        id="S4",
        name="no memory growth (least-squares slope)",
        passed=passed,
        measured=f"{slope:.3f} MB/min over {span_min:.1f} min ({n} ticks)",
        limit=limit,
        note=note,
    )


def check_s5_gaps(ticks: list[Tick], config: SoakConfig) -> CheckResult:
    gaps = [(b.t - a.t).total_seconds() for a, b in itertools.pairwise(ticks)]
    if not gaps:
        return CheckResult(
            "S5",
            "no tick gap above limit",
            False,
            "only one tick",
            f"<= {config.max_tick_gap_s:g} s",
        )
    index = int(np.argmax(gaps))
    worst = gaps[index]
    return CheckResult(
        id="S5",
        name="no tick gap above limit",
        passed=worst <= config.max_tick_gap_s,
        measured=f"max gap {worst:.2f} s, ending at {ticks[index + 1].t.isoformat()}",
        limit=f"<= {config.max_tick_gap_s:g} s",
    )


def check_s6_duration(ticks: list[Tick], config: SoakConfig) -> CheckResult:
    span_min = (ticks[-1].t - ticks[0].t).total_seconds() / 60.0
    return CheckResult(
        id="S6",
        name="run lasted long enough",
        passed=span_min >= config.min_duration_min,
        measured=f"tick span {span_min:.1f} min",
        limit=f">= {config.min_duration_min:g} min",
    )


def run_checks(telemetry: Telemetry, config: SoakConfig, allow_no_audit: bool) -> list[CheckResult]:
    ticks = telemetry.ticks
    return [
        check_s1_cap(ticks),
        check_s2_shutdown(telemetry.shutdown_live, telemetry.audit_found, allow_no_audit),
        check_s3_bookkeeping(ticks),
        check_s4_leak(ticks, config),
        check_s5_gaps(ticks, config),
        check_s6_duration(ticks, config),
    ]


# --- report -----------------------------------------------------------------------------------


def build_report_md(
    source: Path, checks: list[CheckResult], telemetry: Telemetry, config: SoakConfig
) -> str:
    overall = all(check.passed for check in checks)
    span = (telemetry.ticks[-1].t - telemetry.ticks[0].t).total_seconds() / 60.0
    lines = [
        f"# Soak report: {source.name}",
        "",
        f"Input: `{source}`, {telemetry.n_records} records, {len(telemetry.ticks)} ticks over "
        f"{span:.1f} min.",
    ]
    if config.provisional:
        lines.append("Thresholds: provisional (plan starting values, not decided; see SOAK.md).")
    lines += [
        "",
        "| Id | Check | Measured | Limit | Result |",
        "|---|---|---|---|---|",
    ]
    for check in checks:
        result = "PASS" if check.passed else "FAIL"
        lines.append(f"| {check.id} | {check.name} | {check.measured} | {check.limit} | {result} |")
    notes = [f"- {check.id}: {check.note}" for check in checks if check.note]
    notes.append(
        "- S7 (forced kill, restart, cleanup) is a manual check; record it in the run notes."
    )
    lines += ["", f"Overall: {'PASS' if overall else 'FAIL'}", "", "Notes:", *notes, ""]
    return "\n".join(lines)


# --- CLI --------------------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.perf.soak",
        description=(
            "Check a live-spawner soak telemetry log (JSON Lines) against S1-S6 and write a "
            "Markdown report. Limits: tests/perf/soak_config.yaml (provisional). "
            "Exit 0 all pass, 1 a check failed, 2 bad input."
        ),
    )
    parser.add_argument("telemetry", type=Path, metavar="TELEMETRY_JSONL")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="YAML",
        help="soak config (default: tests/perf/soak_config.yaml)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="MD",
        help="write the report here (default: print it to stdout)",
    )
    parser.add_argument(
        "--no-audit",
        action="store_true",
        help="allow a missing audit event in S2 (the audit was not done)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        records = read_palmlive_log(args.telemetry)
        telemetry = parse_telemetry(records)
        checks = run_checks(telemetry, config, allow_no_audit=args.no_audit)
    except PalmfixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code

    report = build_report_md(args.telemetry, checks, telemetry, config)
    overall = all(check.passed for check in checks)
    if args.out is None:
        print(report)
    else:
        try:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(report, encoding="utf-8")
        except OSError as exc:
            print(f"error: cannot write {args.out}: {exc}", file=sys.stderr)
            return SoakInputError.exit_code
        print(f"{'PASS' if overall else 'FAIL'} {args.telemetry} -> {args.out}")
    return EXIT_OK if overall else EXIT_CHECK_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
