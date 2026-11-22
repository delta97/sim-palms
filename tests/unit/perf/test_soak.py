"""Self-tests for tests/perf/soak.py: one passing 61-minute run, one failing case per check S1-S6,
input errors, config and the report file.

Telemetry is generated in each test with a fixed seed (no large committed files). The format
example in tests/fixtures/perf/soak/format_example.jsonl is synthetic and only checked for parsing.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from palmcore.errors import EXIT_CONFIG
from tests.helpers.fixtures import fixture_path
from tests.perf.soak import (
    DEFAULT_CONFIG,
    SoakConfig,
    SoakInputError,
    Tick,
    build_report_md,
    leak_slope,
    load_config,
    main,
    parse_telemetry,
    read_palmlive_log,
    run_checks,
)

START = datetime(2027, 3, 1, 14, 0, 0, tzinfo=UTC)
SEED = 14
BASE_LIVE = 800
CAP = 2000


def make_records(
    *,
    duration_min: float = 61.0,
    live_at: dict[int, int] | None = None,
    mem_slope_mb_per_min: float = 0.0,
    spawned_bump_at: int | None = None,
    gap_at: int | None = None,
    gap_s: float = 0.0,
    shutdown_live: int = 0,
    audit_found: int | None = 0,
    cap: int = CAP,
) -> list[dict[str, Any]]:
    """Synthetic palmlive-format records at 1 Hz. Counts agree unless a knob breaks them."""
    rng = np.random.default_rng(SEED)
    overrides = live_at or {}
    n_ticks = round(duration_min * 60) + 1
    records: list[dict[str, Any]] = []
    offset_s = 0.0
    for i in range(n_ticks):
        if gap_at is not None and i == gap_at:
            offset_s += gap_s
        when = START + timedelta(seconds=i + offset_s)
        live = overrides.get(i, BASE_LIVE + round(60 * math.sin(i / 90.0)))
        spawned_base = 1000 + i
        spawned = spawned_base + (1 if i == spawned_bump_at else 0)
        mem = 180.0 + mem_slope_mb_per_min * (i / 60.0) + float(rng.normal(0.0, 0.2))
        records.append(
            {
                "t": _iso(when),
                "event": "tick",
                "live": live,
                "cap": cap,
                "spawned_total": spawned,
                "removed_total": spawned_base - live,
                "pending_create": 0,
                "agl_m": 210.0,
                "radius_m": 2300.0,
                "proc_private_mb": round(mem, 3),
            }
        )
    end = START + timedelta(seconds=n_ticks - 1 + offset_s + 1)
    records.append({"t": _iso(end), "event": "shutdown_begin"})
    records.append(
        {
            "t": _iso(end + timedelta(milliseconds=500)),
            "event": "shutdown_complete",
            "live": shutdown_live,
        }
    )
    if audit_found is not None:
        records.append(
            {
                "t": _iso(end + timedelta(seconds=1)),
                "event": "audit",
                "palm_objects_found": audit_found,
            }
        )
    return records


def _iso(when: datetime) -> str:
    return when.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write_log(path: Path, records: list[dict[str, Any]]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def failing_ids(path: Path, allow_no_audit: bool = False) -> set[str]:
    telemetry = parse_telemetry(read_palmlive_log(path))
    checks = run_checks(telemetry, load_config(), allow_no_audit=allow_no_audit)
    return {check.id for check in checks if not check.passed}


# --- the passing run --------------------------------------------------------------------------


def test_passing_61_minute_log(tmp_path: Path) -> None:
    path = write_log(tmp_path / "pass.jsonl", make_records())
    telemetry = parse_telemetry(read_palmlive_log(path))
    checks = run_checks(telemetry, load_config(), allow_no_audit=False)
    assert [c.id for c in checks] == ["S1", "S2", "S3", "S4", "S5", "S6"]
    assert all(c.passed for c in checks), [(c.id, c.measured) for c in checks if not c.passed]
    assert main([str(path)]) == 0


def test_report_has_one_line_per_check_and_provisional_note(tmp_path: Path) -> None:
    path = write_log(tmp_path / "pass.jsonl", make_records())
    telemetry = parse_telemetry(read_palmlive_log(path))
    config = load_config()
    checks = run_checks(telemetry, config, allow_no_audit=False)
    report = build_report_md(path, checks, telemetry, config)
    for check_id in ("S1", "S2", "S3", "S4", "S5", "S6"):
        assert f"| {check_id} |" in report
    assert "Thresholds: provisional" in report
    assert "Overall: PASS" in report


def test_leak_slope_is_exact_on_a_line() -> None:
    ticks = [_tick(START + timedelta(minutes=m), 180.0 + 2.0 * m) for m in range(0, 61)]
    slope, span, n = leak_slope(ticks, 30.0)
    assert slope == pytest.approx(2.0, abs=1e-9)
    assert span == pytest.approx(30.0)
    assert n == 31


def _tick(when: datetime, mem: float) -> Tick:
    return Tick(
        t=when, live=800, cap=CAP, spawned_total=1000, removed_total=200, proc_private_mb=mem
    )


# --- one failing case per check ---------------------------------------------------------------


def test_s1_live_over_cap(tmp_path: Path) -> None:
    path = write_log(tmp_path / "s1.jsonl", make_records(live_at={1200: CAP + 1}))
    assert failing_ids(path) == {"S1"}


def test_s2_live_after_shutdown(tmp_path: Path) -> None:
    path = write_log(tmp_path / "s2a.jsonl", make_records(shutdown_live=3))
    assert failing_ids(path) == {"S2"}


def test_s2_audit_finds_palms(tmp_path: Path) -> None:
    path = write_log(tmp_path / "s2b.jsonl", make_records(audit_found=2))
    assert failing_ids(path) == {"S2"}


def test_s2_audit_missing_fails_unless_no_audit(tmp_path: Path) -> None:
    path = write_log(tmp_path / "s2c.jsonl", make_records(audit_found=None))
    assert failing_ids(path) == {"S2"}
    assert failing_ids(path, allow_no_audit=True) == set()
    assert main([str(path), "--no-audit"]) == 0
    assert main([str(path)]) == 1


def test_s3_bookkeeping_mismatch(tmp_path: Path) -> None:
    path = write_log(tmp_path / "s3.jsonl", make_records(spawned_bump_at=1800))
    assert failing_ids(path) == {"S3"}


def test_s4_memory_growth(tmp_path: Path) -> None:
    path = write_log(tmp_path / "s4.jsonl", make_records(mem_slope_mb_per_min=2.0))
    assert failing_ids(path) == {"S4"}
    telemetry = parse_telemetry(read_palmlive_log(path))
    slope, _, _ = leak_slope(telemetry.ticks, load_config().leak_window_min)
    assert slope == pytest.approx(2.0, abs=0.05)


def test_s5_twelve_second_gap(tmp_path: Path) -> None:
    path = write_log(tmp_path / "s5.jsonl", make_records(gap_at=1500, gap_s=11.0))
    assert failing_ids(path) == {"S5"}


def test_s6_only_thirty_minutes(tmp_path: Path) -> None:
    path = write_log(tmp_path / "s6.jsonl", make_records(duration_min=30.0))
    assert failing_ids(path) == {"S6"}
    assert main([str(path)]) == 1


def test_s4_window_shorter_than_leak_window(tmp_path: Path) -> None:
    path = write_log(tmp_path / "s4short.jsonl", make_records(duration_min=20.0))
    assert failing_ids(path) == {"S4", "S6"}


# --- input and config errors (exit 2) ---------------------------------------------------------


def test_missing_file_is_input_error(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope.jsonl")]) == EXIT_CONFIG


def test_invalid_json_line_reports_line_number(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text('{"t": "2027-03-01T14:00:00Z", "event": "tick"\n', encoding="utf-8")
    with pytest.raises(SoakInputError, match=r":1: invalid JSON"):
        read_palmlive_log(path)
    assert main([str(path)]) == EXIT_CONFIG


def test_missing_field_is_input_error(tmp_path: Path) -> None:
    records = make_records()
    del records[5]["proc_private_mb"]
    path = write_log(tmp_path / "field.jsonl", records)
    assert main([str(path)]) == EXIT_CONFIG


def test_non_integer_count_is_input_error(tmp_path: Path) -> None:
    records = make_records()
    records[3]["live"] = 812.5
    path = write_log(tmp_path / "float.jsonl", records)
    assert main([str(path)]) == EXIT_CONFIG


def test_no_tick_events_is_input_error(tmp_path: Path) -> None:
    records = [r for r in make_records() if r["event"] != "tick"]
    path = write_log(tmp_path / "noticks.jsonl", records)
    assert main([str(path)]) == EXIT_CONFIG


def test_time_going_backwards_is_input_error(tmp_path: Path) -> None:
    records = make_records()
    records[100]["t"] = _iso(START)
    path = write_log(tmp_path / "back.jsonl", records)
    assert main([str(path)]) == EXIT_CONFIG


def test_naive_timestamp_is_input_error(tmp_path: Path) -> None:
    records = make_records()
    records[0]["t"] = "2027-03-01T14:00:00.000"
    path = write_log(tmp_path / "naive.jsonl", records)
    assert main([str(path)]) == EXIT_CONFIG


def test_bad_config_is_input_error(tmp_path: Path) -> None:
    path = write_log(tmp_path / "pass.jsonl", make_records())
    config = tmp_path / "soak_config.yaml"
    config.write_text("provisional: true\nleak_window_min: 30\n", encoding="utf-8")
    assert main([str(path), "--config", str(config)]) == EXIT_CONFIG


def test_unknown_events_are_ignored(tmp_path: Path) -> None:
    records = make_records()
    records.insert(10, {"t": _iso(START + timedelta(seconds=9)), "event": "future_event", "x": 1})
    path = write_log(tmp_path / "extra.jsonl", records)
    assert failing_ids(path) == set()


# --- config, fixture and CLI ------------------------------------------------------------------


def test_default_config_matches_plan_values() -> None:
    config = load_config(DEFAULT_CONFIG)
    assert config == SoakConfig(
        provisional=True,
        leak_window_min=30.0,
        leak_mb_per_min_max=1.0,
        max_tick_gap_s=5.0,
        min_duration_min=60.0,
    )


def test_format_example_fixture_parses() -> None:
    records = read_palmlive_log(fixture_path("perf", "soak/format_example.jsonl"))
    telemetry = parse_telemetry(records)
    assert len(telemetry.ticks) == 2
    assert telemetry.shutdown_live == [0]
    assert telemetry.audit_found == [0]


def test_out_writes_markdown_report(tmp_path: Path) -> None:
    path = write_log(tmp_path / "pass.jsonl", make_records())
    out = tmp_path / "soak" / "report.md"
    assert main([str(path), "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    assert "| S4 |" in text and "Overall: PASS" in text


def test_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
