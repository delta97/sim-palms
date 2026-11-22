"""Compare the nofix, static and live captures of one perf run folder (TEST-013).

Plan: plans/detailed/06-testing.md#run-comparison and #perf-capture-format.

    python -m tests.perf.compare tests/perf/runs/<id> [--captures <dir>] [--config <yaml>]

Steps: metrics for every captures/<variant>_r<n>.csv (written to metrics.json), an outlier rule per
variant, the mean over kept runs, deltas against nofix, the budget check from perf_config.yaml, then
report.md and report.json. The report copies run.yaml and says "budget provisional" while
budget.provisional is true.

Exit codes: 0 all budget checks pass, 1 a budget check fails, 2 bad input (missing run.yaml,
captures folder or nofix captures), 3 unstable (a variant has more than one dropped run or fewer
than min_kept kept runs; the report says "unstable: rerun"). Unstable wins over a budget failure
because means over unreliable runs cannot be trusted.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import numpy as np
import yaml

from palmcore.errors import EXIT_OK, ConfigError, PalmfixError
from palmcore.log import get_logger
from tests.perf.frametimes import (
    BudgetSettings,
    OutlierSettings,
    PerfConfig,
    capture_metrics,
    load_config,
)

logger = get_logger(__name__)

VARIANTS: Final = ("nofix", "static", "live")
BASELINE: Final = "nofix"
COMPARED: Final = ("static", "live")
CAPTURE_RE: Final = re.compile(r"^(?P<variant>nofix|static|live)_r(?P<rep>[1-9][0-9]*)\.csv$")
METRIC_KEYS: Final = (
    "avg_frametime_ms",
    "avg_fps",
    "median_frametime_ms",
    "p99_frametime_ms",
    "low1_fps",
    "stutter_count",
    "stutter_per_min",
    "duration_s",
)

EXIT_BUDGET_FAIL: Final = 1
EXIT_UNSTABLE: Final = 3


@dataclass(frozen=True)
class CaptureFile:
    variant: str
    rep: int
    path: Path


@dataclass(frozen=True)
class OutlierResult:
    kept: tuple[str, ...]
    dropped: tuple[str, ...]
    median_ms: float
    unstable: bool


@dataclass(frozen=True)
class VariantSummary:
    variant: str
    runs: tuple[str, ...]
    outliers: OutlierResult
    means: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Check:
    variant: str
    name: str
    value: float | None
    limit: float | None
    result: str  # pass, fail, report (no limit set), or n/a (not evaluated)


@dataclass(frozen=True)
class CompareResult:
    run: dict[str, Any]
    config: PerfConfig
    records: list[dict[str, Any]]
    ignored: list[str]
    summaries: dict[str, VariantSummary]
    checks: list[Check]
    status: str  # pass, fail, unstable
    exit_code: int


# --- discovery and run.yaml -------------------------------------------------------------------


def load_run_yaml(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "run.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{path}: run.yaml not found") from None
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ConfigError(f"{path}: cannot read run.yaml: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: run.yaml must be a mapping")
    return data


def discover_captures(captures_dir: Path) -> tuple[list[CaptureFile], list[str]]:
    """Return the <variant>_r<n>.csv captures, sorted, and the names of ignored files."""
    if not captures_dir.is_dir():
        raise ConfigError(f"{captures_dir}: captures folder not found")
    found: list[CaptureFile] = []
    ignored: list[str] = []
    for path in sorted(captures_dir.iterdir()):
        if not path.is_file():
            continue
        match = CAPTURE_RE.match(path.name)
        if match is None:
            ignored.append(path.name)
            continue
        found.append(CaptureFile(match["variant"], int(match["rep"]), path))
    found.sort(key=lambda c: (VARIANTS.index(c.variant), c.rep))
    return found, ignored


# --- outliers and means -----------------------------------------------------------------------


def apply_outliers(avg_frametime: dict[str, float], settings: OutlierSettings) -> OutlierResult:
    """Drop runs whose avg frametime deviates from the variant median by more than rel_dev."""
    median = float(np.median(list(avg_frametime.values())))
    dropped = tuple(
        name
        for name, value in avg_frametime.items()
        if abs(value - median) / median > settings.rel_dev
    )
    kept = tuple(name for name in avg_frametime if name not in dropped)
    unstable = len(dropped) > 1 or len(kept) < settings.min_kept
    return OutlierResult(kept=kept, dropped=dropped, median_ms=median, unstable=unstable)


def summarise_variant(
    variant: str, records: list[dict[str, Any]], settings: OutlierSettings
) -> VariantSummary:
    by_run = {str(r["run"]): float(r["avg_frametime_ms"]) for r in records}
    outliers = apply_outliers(by_run, settings)
    means: dict[str, float] = {}
    if outliers.kept:
        kept_records = [r for r in records if str(r["run"]) in outliers.kept]
        for key in METRIC_KEYS:
            means[key] = float(np.mean([float(r[key]) for r in kept_records]))
    return VariantSummary(
        variant=variant,
        runs=tuple(by_run),
        outliers=outliers,
        means=means,
    )


# --- budget -----------------------------------------------------------------------------------


def _pct_change(new: float, base: float) -> float:
    return 100.0 * (new - base) / base


def budget_checks(summaries: dict[str, VariantSummary], budget: BudgetSettings) -> list[Check]:
    """Checks for static and live against nofix, one row per budget line."""
    checks: list[Check] = []
    base = summaries[BASELINE]
    for variant in COMPARED:
        summary = summaries.get(variant)
        if summary is None:
            continue
        if not summary.means or not base.means:
            checks.append(Check(variant, "all lines", None, None, "n/a"))
            continue
        delta_ft = _pct_change(summary.means["avg_frametime_ms"], base.means["avg_frametime_ms"])
        checks.append(
            Check(
                variant,
                "frametime delta % (max)",
                delta_ft,
                budget.frametime_pct_max,
                "pass" if delta_ft <= budget.frametime_pct_max else "fail",
            )
        )
        base_stutter = base.means["stutter_count"]
        stutter_limit = base_stutter + max(
            budget.stutter_abs_tol, budget.stutter_rel_tol * base_stutter
        )
        stutter = summary.means["stutter_count"]
        checks.append(
            Check(
                variant,
                "stutter count (max, no added stutter)",
                stutter,
                stutter_limit,
                "pass" if stutter <= stutter_limit else "fail",
            )
        )
        drop = -_pct_change(summary.means["low1_fps"], base.means["low1_fps"])
        if budget.low1_drop_pct_max is None:
            checks.append(Check(variant, "1% low drop % (reported only)", drop, None, "report"))
        else:
            checks.append(
                Check(
                    variant,
                    "1% low drop % (max)",
                    drop,
                    budget.low1_drop_pct_max,
                    "pass" if drop <= budget.low1_drop_pct_max else "fail",
                )
            )
    return checks


# --- orchestration ----------------------------------------------------------------------------


def compare_run(
    run_dir: Path, captures_dir: Path | None = None, config_path: Path | None = None
) -> CompareResult:
    run = load_run_yaml(run_dir)
    config = load_config(config_path)
    folder = captures_dir if captures_dir is not None else run_dir / "captures"
    captures, ignored = discover_captures(folder)
    if not any(c.variant == BASELINE for c in captures):
        raise ConfigError(
            f"{folder}: no {BASELINE}_r<n>.csv captures; the no-fix baseline is required"
        )

    records: list[dict[str, Any]] = []
    for capture in captures:
        metrics = capture_metrics(capture.path, config)
        records.append(
            {
                "run": f"{capture.variant}_r{capture.rep}",
                "variant": capture.variant,
                "rep": capture.rep,
                "file": capture.path.name,
                **metrics,
            }
        )

    summaries: dict[str, VariantSummary] = {}
    for variant in VARIANTS:
        group = [r for r in records if r["variant"] == variant]
        if group:
            summaries[variant] = summarise_variant(variant, group, config.outliers)

    checks = budget_checks(summaries, config.budget)
    if any(s.outliers.unstable for s in summaries.values()):
        status, code = "unstable", EXIT_UNSTABLE
    elif any(c.result == "fail" for c in checks):
        status, code = "fail", EXIT_BUDGET_FAIL
    else:
        status, code = "pass", EXIT_OK
    return CompareResult(
        run=run,
        config=config,
        records=records,
        ignored=ignored,
        summaries=summaries,
        checks=checks,
        status=status,
        exit_code=code,
    )


# --- report -----------------------------------------------------------------------------------


def _fmt(value: float | None, digits: int = 2) -> str:
    return "-" if value is None else f"{value:.{digits}f}"


def _status_line(result: CompareResult) -> str:
    if result.status == "unstable":
        return "UNSTABLE: rerun"
    return result.status.upper()


def build_metrics_json(result: CompareResult) -> dict[str, Any]:
    return {
        "budget_provisional": result.config.budget.provisional,
        "captures": result.records,
        "ignored_files": result.ignored,
    }


def build_report_json(result: CompareResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "exit_code": result.exit_code,
        "budget_provisional": result.config.budget.provisional,
        "run": result.run,
        "variants": {
            name: {
                "runs": list(s.runs),
                "kept": list(s.outliers.kept),
                "dropped": list(s.outliers.dropped),
                "unstable": s.outliers.unstable,
                "median_avg_frametime_ms": s.outliers.median_ms,
                "means": s.means,
            }
            for name, s in result.summaries.items()
        },
        "checks": [
            {
                "variant": c.variant,
                "check": c.name,
                "value": c.value,
                "limit": c.limit,
                "result": c.result,
            }
            for c in result.checks
        ],
    }


def build_report_md(result: CompareResult, run_dir_name: str) -> str:
    out: list[str] = [f"# Frametime comparison: {run_dir_name}", ""]
    out.append(f"**Status: {_status_line(result)}**")
    out.append("")
    if result.config.budget.provisional:
        out.append(
            "**Budget provisional.** The budget values are the plan's starting values and DEC-005 "
            "is not decided. Set `budget.provisional: false` in perf_config.yaml when it is."
        )
        out.append("")
    if result.status == "unstable":
        out.append("Unstable: rerun. A variant has too many dropped runs or too few kept runs.")
        out.append("")

    out += ["## Run (copied from run.yaml)", "", "```yaml"]
    out.append(yaml.safe_dump(result.run, sort_keys=False).rstrip())
    out += ["```", ""]

    out += [
        "## Means over kept runs",
        "",
        "| Variant | Runs | Kept | Dropped | Avg FPS | Avg frametime ms | 1% low FPS | "
        "p99 frametime ms | Stutter count | Stutter / min |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for variant in VARIANTS:
        s = result.summaries.get(variant)
        if s is None:
            continue
        m = s.means
        out.append(
            "| "
            + " | ".join(
                [
                    variant,
                    str(len(s.runs)),
                    str(len(s.outliers.kept)),
                    ", ".join(s.outliers.dropped) or "none",
                    _fmt(m.get("avg_fps")),
                    _fmt(m.get("avg_frametime_ms"), 3),
                    _fmt(m.get("low1_fps")),
                    _fmt(m.get("p99_frametime_ms"), 3),
                    _fmt(m.get("stutter_count"), 1),
                    _fmt(m.get("stutter_per_min"), 2),
                ]
            )
            + " |"
        )
    out.append("")

    out += ["## Budget checks (against nofix)", "", "| Variant | Check | Value | Limit | Result |"]
    out += ["| --- | --- | --- | --- | --- |"]
    for c in result.checks:
        out.append(
            f"| {c.variant} | {c.name} | {_fmt(c.value, 3)} | {_fmt(c.limit, 3)} | {c.result} |"
        )
    if not result.checks:
        out.append("| - | no static or live captures | - | - | n/a |")
    out.append("")

    out += ["## Outliers", ""]
    dropped_any = False
    for name, s in result.summaries.items():
        for run in s.outliers.dropped:
            dropped_any = True
            rec = next(r for r in result.records if r["run"] == run)
            dev = 100.0 * abs(rec["avg_frametime_ms"] - s.outliers.median_ms) / s.outliers.median_ms
            out.append(
                f"- Dropped {run}: avg frametime {rec['avg_frametime_ms']:.3f} ms vs variant "
                f"median {s.outliers.median_ms:.3f} ms ({dev:.1f}% off; rule: more than "
                f"{100 * result.config.outliers.rel_dev:.0f}%)."
            )
        if s.outliers.unstable:
            out.append(f"- {name}: unstable (kept {len(s.outliers.kept)} of {len(s.runs)} runs).")
    if not dropped_any:
        out.append("- None.")
    out.append("")

    if result.ignored:
        out += ["## Ignored files", ""]
        out += [f"- {name}" for name in result.ignored]
        out.append("")
    return "\n".join(out) + "\n"


def write_outputs(result: CompareResult, run_dir: Path) -> None:
    def _dump(name: str, payload: dict[str, Any]) -> None:
        (run_dir / name).write_text(
            json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
        )

    _dump("metrics.json", build_metrics_json(result))
    _dump("report.json", build_report_json(result))
    (run_dir / "report.md").write_text(build_report_md(result, run_dir.name), encoding="utf-8")


# --- CLI --------------------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.perf.compare",
        description=(
            "Compute metrics for every captures/<variant>_r<n>.csv in a run folder, write "
            "metrics.json, report.md and report.json, and check the budget from perf_config.yaml. "
            "Exit 0 pass, 1 budget fail, 2 bad input, 3 unstable."
        ),
    )
    parser.add_argument("run_dir", type=Path, metavar="RUN_DIR")
    parser.add_argument(
        "--captures",
        type=Path,
        default=None,
        metavar="DIR",
        help="captures folder (default: RUN_DIR/captures)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="YAML",
        help="perf config (default: tests/perf/perf_config.yaml)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    run_dir: Path = args.run_dir
    try:
        if not run_dir.is_dir():
            raise ConfigError(f"{run_dir}: run folder not found")
        result = compare_run(run_dir, captures_dir=args.captures, config_path=args.config)
        write_outputs(result, run_dir)
    except PalmfixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    print(f"{_status_line(result)} {run_dir}")
    for check in result.checks:
        print(f"  {check.variant}: {check.name} = {_fmt(check.value, 3)} -> {check.result}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
