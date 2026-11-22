"""Self-tests for tests/perf/frametimes.py: formulas, trim, bad rows, columns and config.

Synthetic data only. Fixtures in tests/fixtures/perf/frametimes/ are hand-written, marked synthetic.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest
import yaml

from palmcore.errors import EXIT_CONFIG
from palmcore.errors import ConfigError as PalmConfigError
from tests.helpers.fixtures import REPO_ROOT, fixture_path
from tests.perf.frametimes import (
    DEFAULT_CONFIG,
    CaptureError,
    PerfConfig,
    capture_metrics,
    compute_metrics,
    load_config,
    main,
    read_frametimes,
    stutter_count,
    trim,
)

FRAME_60HZ_MS = 1000.0 / 60.0


def _config(trim_start_s: float = 0.0, trim_end_s: float = 0.0, **overrides: object) -> PerfConfig:
    """The repo default config with the trim set for short synthetic data."""
    base = load_config(DEFAULT_CONFIG)
    capture = dataclasses.replace(
        base.capture, trim_start_s=trim_start_s, trim_end_s=trim_end_s, **overrides
    )
    return dataclasses.replace(base, capture=capture)


def _write_csv(path: Path, frametimes: list[float], header: str = "MsBetweenPresents") -> Path:
    lines = [header, *(f"{value:.6f}" for value in frametimes)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_constant_60fps_metrics() -> None:
    ft = np.full(3000, FRAME_60HZ_MS)
    metrics = compute_metrics(ft, _config())
    assert metrics["avg_fps"] == pytest.approx(60.0, abs=0.01)
    assert metrics["avg_frametime_ms"] == pytest.approx(FRAME_60HZ_MS)
    assert metrics["stutter_count"] == 0
    assert metrics["p99_frametime_ms"] == pytest.approx(FRAME_60HZ_MS)
    assert metrics["n_frames"] == 3000


def test_one_slow_frame_in_100() -> None:
    ft = np.array([10.0] * 99 + [50.0])
    metrics = compute_metrics(ft, _config())
    assert metrics["avg_frametime_ms"] == pytest.approx(10.4)
    assert metrics["stutter_count"] == 1
    # ceil(0.01 * 100) = 1 slowest frame: 1000 / 50 ms.
    assert metrics["low1_fps"] == pytest.approx(20.0)
    assert metrics["p99_frametime_ms"] == pytest.approx(
        float(np.percentile(ft, 99, method="linear"))
    )
    assert metrics["avg_fps"] == pytest.approx(1000.0 * 100 / 1040.0)
    assert metrics["median_frametime_ms"] == pytest.approx(10.0)
    assert metrics["duration_s"] == pytest.approx(1.04)
    assert metrics["stutter_per_min"] == pytest.approx(1 / (1.04 / 60.0))


def test_low1_uses_ceiling_of_one_percent() -> None:
    # N = 101 -> ceil(1.01) = 2 slowest frames: (50 + 40) / 2 = 45 ms.
    ft = np.array([10.0] * 99 + [40.0, 50.0])
    metrics = compute_metrics(ft, _config())
    assert metrics["low1_fps"] == pytest.approx(1000.0 / 45.0)


def test_trim_start_removes_first_5_seconds() -> None:
    ft = np.full(2000, 10.0)  # 20 s of 10 ms frames
    kept, start = trim(ft, np.arange(2000) * 10.0, trim_start_s=5.0, trim_end_s=0.0)
    assert kept.size == 1500
    assert start[0] == pytest.approx(5000.0)


def test_trim_end_removes_last_seconds() -> None:
    ft = np.full(2000, 10.0)
    kept, start = trim(ft, np.arange(2000) * 10.0, trim_start_s=5.0, trim_end_s=2.0)
    # Frames start in [5000, 18000) ms: 1300 frames.
    assert kept.size == 1300
    assert start[-1] < 18000.0


def test_trim_that_removes_everything_is_an_error() -> None:
    with pytest.raises(CaptureError, match="no frames left"):
        trim(np.full(10, 10.0), np.arange(10) * 10.0, trim_start_s=5.0, trim_end_s=0.0)


def test_placeholder_columns_fixture_drops_bad_rows() -> None:
    path = fixture_path("perf", "frametimes/presentmon_placeholder_columns.csv")
    raw = read_frametimes(path, _config())
    assert raw.column == "MsBetweenPresents"
    assert raw.n_dropped_rows == 2  # "n/a" and "0"
    assert raw.frametimes_ms.tolist() == pytest.approx([16.7, 16.6, 33.4, 16.7])

    metrics = capture_metrics(path, _config())
    assert metrics["n_frames"] == 4
    assert metrics["avg_frametime_ms"] == pytest.approx(83.4 / 4)
    assert metrics["n_dropped_rows"] == 2


def test_second_placeholder_column_fixture() -> None:
    path = fixture_path("perf", "frametimes/capfx_frametime_column.csv")
    metrics = capture_metrics(path, _config())
    assert metrics["column"] == "FrameTime"
    assert metrics["n_frames"] == 5
    assert metrics["avg_frametime_ms"] == pytest.approx(18.0)
    assert metrics["low1_fps"] == pytest.approx(20.0)
    assert metrics["stutter_count"] == 1
    assert metrics["n_dropped_rows"] == 0


def test_first_present_column_wins(tmp_path: Path) -> None:
    path = tmp_path / "both.csv"
    path.write_text("FrameTime,MsBetweenPresents\n10,20\n10,20\n", encoding="utf-8")
    # Config order decides: MsBetweenPresents is listed first, so it is used even though both exist.
    config = _config(frametime_columns=("MsBetweenPresents", "FrameTime"))
    raw = read_frametimes(path, config)
    assert raw.column == "MsBetweenPresents"
    assert raw.frametimes_ms.tolist() == [20.0, 20.0]


def test_missing_frametime_column_is_a_config_error(tmp_path: Path) -> None:
    path = _write_csv(tmp_path / "other.csv", [10.0], header="Foo")
    with pytest.raises(CaptureError, match=r"perf_config\.yaml"):
        read_frametimes(path, _config())


def test_missing_file_is_a_capture_error(tmp_path: Path) -> None:
    with pytest.raises(CaptureError, match="not found"):
        read_frametimes(tmp_path / "nope.csv", _config())


def test_comment_lines_and_blank_lines_are_skipped(tmp_path: Path) -> None:
    path = tmp_path / "c.csv"
    path.write_text("// note\n\nMsBetweenPresents\n10.0\n// another\n12.0\n", encoding="utf-8")
    raw = read_frametimes(path, _config())
    assert raw.frametimes_ms.tolist() == [10.0, 12.0]


def test_time_column_sets_frame_start_times(tmp_path: Path) -> None:
    path = tmp_path / "t.csv"
    path.write_text("MsBetweenPresents,TimeInSeconds\n10,0\n10,0.02\n20,0.03\n", encoding="utf-8")
    config = _config(time_column="TimeInSeconds", time_unit="s")
    raw = read_frametimes(path, config)
    assert raw.start_ms.tolist() == pytest.approx([0.0, 20.0, 30.0])


def test_rolling_stutter_baseline_differs_from_global() -> None:
    # 1000 frames at 10 ms, then 1000 at 30 ms, with one 25 ms frame in the first section.
    ft = np.concatenate([np.full(1000, 10.0), np.full(1000, 30.0)])
    ft[500] = 25.0
    start = np.concatenate(([0.0], np.cumsum(ft)[:-1]))
    base = _config()
    global_cfg = dataclasses.replace(
        base, stutter=dataclasses.replace(base.stutter, baseline="global")
    )
    rolling_cfg = dataclasses.replace(
        base, stutter=dataclasses.replace(base.stutter, baseline="rolling")
    )
    # Global median is 20 ms, so the threshold is 40 ms and the 25 ms frame is not a stutter.
    assert stutter_count(ft, start, global_cfg.stutter) == 0
    # Rolling median near 5 s is 10 ms, so the threshold is 20 ms and the frame is flagged.
    assert stutter_count(ft, start, rolling_cfg.stutter) >= 1


def test_constant_frames_have_no_stutter_with_rolling_baseline() -> None:
    base = _config()
    rolling = dataclasses.replace(
        base, stutter=dataclasses.replace(base.stutter, baseline="rolling")
    )
    ft = np.full(600, FRAME_60HZ_MS)
    start = np.arange(600) * FRAME_60HZ_MS
    assert stutter_count(ft, start, rolling.stutter) == 0


def test_config_missing_key_is_rejected(tmp_path: Path) -> None:
    data = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    del data["stutter"]
    path = tmp_path / "perf_config.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(PalmConfigError, match="stutter"):
        load_config(path)


def test_default_config_is_provisional() -> None:
    config = load_config(DEFAULT_CONFIG)
    assert config.budget.provisional is True
    assert config.budget.frametime_pct_max == pytest.approx(5.0)
    assert config.capture.frametime_columns == (
        "MsBetweenPresents",
        "FrameTime",
        "msBetweenPresents",
    )
    assert config.budget.low1_drop_pct_max is None


def test_cli_prints_metrics_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "perf_config.yaml"
    data = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    data["capture"]["trim_start_s"] = 0
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    capture = fixture_path("perf", "frametimes/capfx_frametime_column.csv")
    assert main([str(capture), "--config", str(config_path)]) == 0
    assert '"avg_frametime_ms": 18.0' in capsys.readouterr().out


def test_cli_bad_input_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(REPO_ROOT / "does_not_exist.csv")]) == EXIT_CONFIG
    assert "not found" in capsys.readouterr().err


def test_cli_help_exits_0() -> None:
    with pytest.raises(SystemExit) as info:
        main(["--help"])
    assert info.value.code == 0
