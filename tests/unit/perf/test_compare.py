"""Self-tests for tests/perf/compare.py: outliers, budget lines, exit codes and report files.

Captures are generated in each test with a fixed seed (no large committed files).
run.yaml comes from tests/fixtures/perf/compare/run.yaml, a synthetic fixture.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from palmcore.errors import EXIT_CONFIG
from tests.helpers.fixtures import fixture_path
from tests.perf.compare import (
    EXIT_BUDGET_FAIL,
    EXIT_UNSTABLE,
    apply_outliers,
    main,
)
from tests.perf.frametimes import OutlierSettings

FRAME_MS = 1000.0 / 60.0
FRAMES = 3600  # about 60 s at 60 Hz; the default 5 s trim removes the first 300 frames


def _write_capture(path: Path, base_ms: float, seed: int, spikes: int = 0) -> None:
    rng = np.random.default_rng(seed)
    ft = base_ms * (1.0 + rng.normal(0.0, 0.005, FRAMES))
    if spikes:
        # Spikes far into the kept section, so the trim does not remove them.
        idx = np.linspace(600, FRAMES - 1, spikes, dtype=int)
        ft[idx] = base_ms * 2.5
    lines = ["MsBetweenPresents", *(f"{value:.6f}" for value in ft)]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _make_run(
    tmp_path: Path,
    plan: dict[str, dict[str, object]],
    ignored: tuple[str, ...] = (),
) -> Path:
    """Build a run folder. ``plan`` maps a capture name to {"base": ms, "spikes": n}."""
    run_dir = tmp_path / "run"
    captures = run_dir / "captures"
    captures.mkdir(parents=True)
    shutil.copy(fixture_path("perf", "compare/run.yaml"), run_dir / "run.yaml")
    for i, (name, spec) in enumerate(sorted(plan.items())):
        _write_capture(
            captures / f"{name}.csv",
            float(spec["base"]),  # type: ignore[arg-type]
            seed=100 + i,
            spikes=int(spec.get("spikes", 0)),  # type: ignore[arg-type]
        )
    for name in ignored:
        (captures / name).write_text("not a capture\n", encoding="utf-8")
    return run_dir


def _clean_plan(static_factor: float = 1.03) -> dict[str, dict[str, object]]:
    plan: dict[str, dict[str, object]] = {}
    for rep in (1, 2, 3):
        plan[f"nofix_r{rep}"] = {"base": FRAME_MS}
        plan[f"static_r{rep}"] = {"base": FRAME_MS * static_factor}
        plan[f"live_r{rep}"] = {"base": FRAME_MS * static_factor}
    return plan


def _report(run_dir: Path) -> dict[str, object]:
    return json.loads((run_dir / "report.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _check(report: dict[str, object], variant: str, name_prefix: str) -> dict[str, object]:
    checks = report["checks"]
    assert isinstance(checks, list)
    for row in checks:
        if row["variant"] == variant and row["check"].startswith(name_prefix):
            return row  # type: ignore[no-any-return]
    raise AssertionError(f"no check {variant} / {name_prefix}")


def test_apply_outliers_drops_one_run_and_is_not_unstable() -> None:
    result = apply_outliers({"a": 10.0, "b": 10.1, "c": 14.0}, OutlierSettings(0.10, 2))
    assert result.dropped == ("c",)
    assert result.kept == ("a", "b")
    assert result.unstable is False


def test_apply_outliers_two_drops_is_unstable() -> None:
    result = apply_outliers({"a": 10.0, "b": 14.0, "c": 20.0}, OutlierSettings(0.10, 2))
    assert len(result.dropped) == 2
    assert result.unstable is True


def test_static_3_percent_slower_passes(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path, _clean_plan(1.03))
    assert main([str(run_dir)]) == 0
    report = _report(run_dir)
    assert report["status"] == "pass"
    assert _check(report, "static", "frametime")["result"] == "pass"
    assert _check(report, "live", "frametime")["result"] == "pass"


def test_static_6_percent_slower_fails_frametime(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path, _clean_plan(1.06))
    assert main([str(run_dir)]) == EXIT_BUDGET_FAIL
    report = _report(run_dir)
    assert report["status"] == "fail"
    frametime = _check(report, "static", "frametime")
    assert frametime["result"] == "fail"
    assert frametime["value"] == pytest.approx(6.0, abs=0.5)


def test_one_planted_outlier_is_dropped_and_noted(tmp_path: Path) -> None:
    plan = _clean_plan(1.03)
    plan["static_r2"] = {"base": FRAME_MS * 1.03 * 1.25}
    run_dir = _make_run(tmp_path, plan)
    assert main([str(run_dir)]) == 0
    report = _report(run_dir)
    variants = report["variants"]
    assert isinstance(variants, dict)
    assert variants["static"]["dropped"] == ["static_r2"]  # type: ignore[index]
    assert "Dropped static_r2" in (run_dir / "report.md").read_text(encoding="utf-8")


def test_two_planted_outliers_is_unstable_exit_3(tmp_path: Path) -> None:
    # Static runs at 1.00x, 1.30x and 1.60x: median 1.30x, so two runs are more than 10% off.
    plan = _clean_plan(1.03)
    plan["static_r1"] = {"base": FRAME_MS}
    plan["static_r2"] = {"base": FRAME_MS * 1.30}
    plan["static_r3"] = {"base": FRAME_MS * 1.60}
    run_dir = _make_run(tmp_path, plan)
    assert main([str(run_dir)]) == EXIT_UNSTABLE
    report = _report(run_dir)
    assert report["status"] == "unstable"
    assert "UNSTABLE: rerun" in (run_dir / "report.md").read_text(encoding="utf-8")


def test_missing_nofix_is_bad_input_exit_2(tmp_path: Path) -> None:
    plan = {name: spec for name, spec in _clean_plan().items() if not name.startswith("nofix")}
    run_dir = _make_run(tmp_path, plan)
    assert main([str(run_dir)]) == EXIT_CONFIG


def test_missing_run_yaml_is_bad_input_exit_2(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path, _clean_plan())
    (run_dir / "run.yaml").unlink()
    assert main([str(run_dir)]) == EXIT_CONFIG


def test_stutter_budget_fails_when_static_adds_stutter(tmp_path: Path) -> None:
    plan = _clean_plan(1.0)
    for rep in (1, 2, 3):
        plan[f"static_r{rep}"] = {"base": FRAME_MS, "spikes": 60}
    run_dir = _make_run(tmp_path, plan)
    assert main([str(run_dir)]) == EXIT_BUDGET_FAIL
    report = _report(run_dir)
    assert _check(report, "static", "stutter")["result"] == "fail"
    assert _check(report, "static", "frametime")["result"] == "pass"


def test_metrics_and_report_files_are_written(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path, _clean_plan(1.03), ignored=("notes.txt",))
    assert main([str(run_dir)]) == 0
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert len(metrics["captures"]) == 9
    assert metrics["ignored_files"] == ["notes.txt"]
    assert metrics["budget_provisional"] is True
    report_md = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "Budget provisional" in report_md
    assert "Run (copied from run.yaml)" in report_md
    assert "synthetic" in report_md


def test_missing_captures_folder_is_bad_input(tmp_path: Path) -> None:
    run_dir = _make_run(tmp_path, _clean_plan())
    assert main([str(run_dir), "--captures", str(tmp_path / "absent")]) == EXIT_CONFIG
