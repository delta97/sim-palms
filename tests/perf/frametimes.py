"""Parse one frametime capture (PresentMon or CapFrameX CSV) and compute its metrics (TEST-013).

Plan: plans/detailed/06-testing.md#frametime-metrics.

    python -m tests.perf.frametimes <capture.csv> [--config <perf_config.yaml>]

Column names, comment prefix, trim and stutter settings come from tests/perf/perf_config.yaml.
The default column names are placeholders. VERIFY (V4, V5): TEST-103 confirms them on real data.

Exit codes follow palmcore: 0 ok, 2 bad input (missing file or config, no usable frametime column,
no frames left after trimming).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np
import yaml
from numpy.typing import NDArray

from palmcore.errors import EXIT_OK, ConfigError, PalmfixError
from palmcore.log import get_logger
from tests.helpers.fixtures import REPO_ROOT

logger = get_logger(__name__)

DEFAULT_CONFIG: Final = REPO_ROOT / "tests" / "perf" / "perf_config.yaml"
FloatArray = NDArray[np.float64]


class CaptureError(ConfigError):
    """A capture cannot be used: missing, unreadable, no frametime column, or no frames left."""


@dataclass(frozen=True)
class CaptureSettings:
    frametime_columns: tuple[str, ...]
    time_column: str | None
    time_unit: str
    comment_prefix: str | None
    trim_start_s: float
    trim_end_s: float


@dataclass(frozen=True)
class StutterSettings:
    factor: float
    baseline: str
    rolling_window_s: float


@dataclass(frozen=True)
class OutlierSettings:
    rel_dev: float
    min_kept: int


@dataclass(frozen=True)
class BudgetSettings:
    provisional: bool
    frametime_pct_max: float
    stutter_abs_tol: float
    stutter_rel_tol: float
    low1_drop_pct_max: float | None


@dataclass(frozen=True)
class PerfConfig:
    capture: CaptureSettings
    stutter: StutterSettings
    outliers: OutlierSettings
    budget: BudgetSettings


@dataclass(frozen=True)
class RawCapture:
    column: str
    frametimes_ms: FloatArray
    start_ms: FloatArray
    n_dropped_rows: int


# --- config -----------------------------------------------------------------------------------


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name)
    if not isinstance(value, dict):
        raise ConfigError(f"perf_config.yaml: section '{name}' is missing or not a mapping")
    return value


def _value(section: dict[str, Any], name: str, key: str) -> Any:
    if key not in section:
        raise ConfigError(f"perf_config.yaml: {name}.{key} is missing")
    return section[key]


def _number(section: dict[str, Any], name: str, key: str, minimum: float | None = None) -> float:
    value = _value(section, name, key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ConfigError(f"perf_config.yaml: {name}.{key} must be a number, got {value!r}")
    if minimum is not None and value < minimum:
        raise ConfigError(f"perf_config.yaml: {name}.{key} must be >= {minimum}, got {value!r}")
    return float(value)


def _optional_number(section: dict[str, Any], name: str, key: str) -> float | None:
    if _value(section, name, key) is None:
        return None
    return _number(section, name, key)


def _optional_text(section: dict[str, Any], name: str, key: str) -> str | None:
    value = _value(section, name, key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ConfigError(f"perf_config.yaml: {name}.{key} must be a non-empty string or null")
    return value


def _choice(section: dict[str, Any], name: str, key: str, options: tuple[str, ...]) -> str:
    value = _value(section, name, key)
    if value not in options:
        raise ConfigError(f"perf_config.yaml: {name}.{key} must be one of {options}, got {value!r}")
    return str(value)


def load_config(path: Path | None = None) -> PerfConfig:
    """Load and validate perf_config.yaml. Every key is required; nothing is defaulted silently."""
    config_path = DEFAULT_CONFIG if path is None else path
    try:
        text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError(f"{config_path}: perf config not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{config_path}: cannot read perf config: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{config_path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{config_path}: top level must be a mapping")

    cap = _section(data, "capture")
    columns = _value(cap, "capture", "frametime_columns")
    if (
        not isinstance(columns, list)
        or not columns
        or not all(isinstance(c, str) and c for c in columns)
    ):
        raise ConfigError("perf_config.yaml: capture.frametime_columns must be a non-empty list")
    capture = CaptureSettings(
        frametime_columns=tuple(columns),
        time_column=_optional_text(cap, "capture", "time_column"),
        time_unit=_choice(cap, "capture", "time_unit", ("s", "ms")),
        comment_prefix=_optional_text(cap, "capture", "comment_prefix"),
        trim_start_s=_number(cap, "capture", "trim_start_s", minimum=0),
        trim_end_s=_number(cap, "capture", "trim_end_s", minimum=0),
    )

    st = _section(data, "stutter")
    stutter = StutterSettings(
        factor=_number(st, "stutter", "factor", minimum=0),
        baseline=_choice(st, "stutter", "baseline", ("global", "rolling")),
        rolling_window_s=_number(st, "stutter", "rolling_window_s", minimum=0),
    )

    ol = _section(data, "outliers")
    outliers = OutlierSettings(
        rel_dev=_number(ol, "outliers", "rel_dev", minimum=0),
        min_kept=int(_number(ol, "outliers", "min_kept", minimum=1)),
    )

    bg = _section(data, "budget")
    provisional = _value(bg, "budget", "provisional")
    if not isinstance(provisional, bool):
        raise ConfigError("perf_config.yaml: budget.provisional must be true or false")
    budget = BudgetSettings(
        provisional=provisional,
        frametime_pct_max=_number(bg, "budget", "frametime_pct_max"),
        stutter_abs_tol=_number(bg, "budget", "stutter_abs_tol", minimum=0),
        stutter_rel_tol=_number(bg, "budget", "stutter_rel_tol", minimum=0),
        low1_drop_pct_max=_optional_number(bg, "budget", "low1_drop_pct_max"),
    )
    return PerfConfig(capture=capture, stutter=stutter, outliers=outliers, budget=budget)


# --- parsing ----------------------------------------------------------------------------------


def _number_at(row: list[str], index: int) -> float | None:
    if index >= len(row):
        return None
    try:
        value = float(row[index])
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def read_frametimes(path: Path, config: PerfConfig) -> RawCapture:
    """Read one capture. Rows with a bad or <= 0 frametime are dropped and counted."""
    cap = config.capture
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise CaptureError(f"{path}: capture file not found") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise CaptureError(f"{path}: cannot read capture: {exc}") from exc

    lines = [line for line in text.splitlines() if line.strip()]
    if cap.comment_prefix is not None:
        lines = [line for line in lines if not line.lstrip().startswith(cap.comment_prefix)]
    if not lines:
        raise CaptureError(f"{path}: no header row found")
    rows = list(csv.reader(lines))
    header = [name.strip() for name in rows[0]]

    column = next((c for c in cap.frametime_columns if c in header), None)
    if column is None:
        raise CaptureError(
            f"{path}: none of {list(cap.frametime_columns)} is a column; header starts with "
            f"{header[:12]}. Set capture.frametime_columns in perf_config.yaml (VERIFY, TEST-103)"
        )
    ft_index = header.index(column)
    t_index: int | None = None
    if cap.time_column is not None:
        if cap.time_column not in header:
            raise CaptureError(f"{path}: time column {cap.time_column!r} is not in the header")
        t_index = header.index(cap.time_column)

    frametimes: list[float] = []
    times: list[float] = []
    dropped = 0
    for row in rows[1:]:
        ft = _number_at(row, ft_index)
        if ft is None or ft <= 0:
            dropped += 1
            continue
        if t_index is not None:
            t = _number_at(row, t_index)
            if t is None:
                dropped += 1
                continue
            times.append(t * (1000.0 if cap.time_unit == "s" else 1.0))
        frametimes.append(ft)

    if not frametimes:
        raise CaptureError(f"{path}: no usable frametime rows in column {column!r}")
    ft_arr = np.asarray(frametimes, dtype=np.float64)
    if t_index is None:
        start = np.concatenate(([0.0], np.cumsum(ft_arr)[:-1]))
    else:
        t_arr = np.asarray(times, dtype=np.float64)
        start = t_arr - t_arr[0]
        if np.any(np.diff(start) < 0):
            raise CaptureError(f"{path}: time column {cap.time_column!r} goes backwards")
    if dropped:
        logger.warning("%s: dropped %d unusable row(s)", path.name, dropped)
    return RawCapture(column=column, frametimes_ms=ft_arr, start_ms=start, n_dropped_rows=dropped)


def trim(
    frametimes_ms: FloatArray, start_ms: FloatArray, trim_start_s: float, trim_end_s: float
) -> tuple[FloatArray, FloatArray]:
    """Keep frames that start at or after trim_start_s and before the end minus trim_end_s."""
    end_ms = float(start_ms[-1] + frametimes_ms[-1])
    keep = (start_ms >= trim_start_s * 1000.0) & (start_ms < end_ms - trim_end_s * 1000.0)
    if not np.any(keep):
        raise CaptureError(
            f"no frames left after trimming {trim_start_s} s from the start and "
            f"{trim_end_s} s from the end"
        )
    return frametimes_ms[keep], start_ms[keep]


# --- metrics ----------------------------------------------------------------------------------


def stutter_count(ft_ms: FloatArray, start_ms: FloatArray, settings: StutterSettings) -> int:
    """Count frames with frametime > factor * baseline (global median or rolling median)."""
    if settings.baseline == "global":
        threshold = settings.factor * float(np.median(ft_ms))
        return int(np.count_nonzero(ft_ms > threshold))
    half_ms = settings.rolling_window_s * 1000.0 / 2.0
    lo = np.searchsorted(start_ms, start_ms - half_ms, side="left")
    hi = np.searchsorted(start_ms, start_ms + half_ms, side="right")
    count = 0
    for i in range(ft_ms.size):
        baseline = float(np.median(ft_ms[lo[i] : hi[i]]))
        if ft_ms[i] > settings.factor * baseline:
            count += 1
    return count


def compute_metrics(
    ft_ms: FloatArray, config: PerfConfig, start_ms: FloatArray | None = None
) -> dict[str, float]:
    """Metrics from trimmed frametimes, per plan 06-testing.md#frametime-metrics."""
    n = int(ft_ms.size)
    if n == 0:
        raise CaptureError("no frames to compute metrics from")
    total_ms = float(np.sum(ft_ms))
    if start_ms is None:
        start_ms = np.concatenate(([0.0], np.cumsum(ft_ms)[:-1]))
    # Average of the slowest ceil(0.01 * N) frames, computed with integers.
    slowest_k = (n + 99) // 100
    slowest = np.sort(ft_ms)[::-1][:slowest_k]
    count = stutter_count(ft_ms, start_ms, config.stutter)
    return {
        "n_frames": float(n),
        "duration_s": total_ms / 1000.0,
        "avg_frametime_ms": total_ms / n,
        "avg_fps": 1000.0 * n / total_ms,
        "median_frametime_ms": float(np.median(ft_ms)),
        "p99_frametime_ms": float(np.percentile(ft_ms, 99, method="linear")),
        "low1_fps": 1000.0 / float(np.mean(slowest)),
        "stutter_count": float(count),
        "stutter_per_min": count / (total_ms / 60000.0),
    }


def capture_metrics(path: Path, config: PerfConfig) -> dict[str, Any]:
    """Read, trim and measure one capture; add the column used and dropped row count."""
    raw = read_frametimes(path, config)
    ft, start = trim(
        raw.frametimes_ms,
        raw.start_ms,
        config.capture.trim_start_s,
        config.capture.trim_end_s,
    )
    metrics: dict[str, Any] = compute_metrics(ft, config, start_ms=start)
    metrics["column"] = raw.column
    metrics["n_dropped_rows"] = raw.n_dropped_rows
    return metrics


# --- CLI --------------------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tests.perf.frametimes",
        description=(
            "Print the frametime metrics of one capture as JSON: avg FPS, 1% low FPS, p99 "
            "frametime, median, stutter count. Trim and stutter settings: perf_config.yaml."
        ),
    )
    parser.add_argument("capture", type=Path, metavar="CAPTURE_CSV")
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
    try:
        config = load_config(args.config)
        metrics = capture_metrics(args.capture, config)
    except PalmfixError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    print(json.dumps({"capture": str(args.capture), **metrics}, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
