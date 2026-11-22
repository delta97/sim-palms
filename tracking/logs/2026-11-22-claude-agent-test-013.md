# Session log: 2026-11-22, claude-agent, test-013

- **Started / ended:** 2026-11-22 (local time)
- **Agent / model / person:** claude-agent (Claude Haiku 5.5)
- **Branch / worktree:** task/test-013-build-the-frametime-capture-parser-and-r, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-013
- **Tasks:** TEST-013 (in_progress -> review)

## Goal

Build the frametime capture parser (`tests/perf/frametimes.py`) and the run comparison report
(`tests/perf/compare.py`) from plan 06-testing.md#frametime-metrics and #run-comparison, so that
the Phase 5 bake-off (LIVE-009) and the TEST-103 dry run have a tested harness.

## What changed

- `tests/perf/perf_config.yaml`: capture, stutter, outlier and budget settings. Column names and
  comment prefix are plan placeholders marked VERIFY. Budget is the plan's starting values with
  `provisional: true` (DEC-005 not decided).
- `tests/perf/frametimes.py`: CSV reader (comment skip, first matching column, dropped rows counted),
  trim, metrics (avg FPS from total ms, 1% low as mean of slowest ceil(N/100) frames, numpy linear
  p99, stutter global or rolling baseline), `capture_metrics`, and a CLI that prints JSON.
- `tests/perf/compare.py`: discovers `<variant>_r<n>.csv`, writes `metrics.json`, applies the
  outlier rule, averages kept runs, checks the budget against nofix, writes `report.md` and
  `report.json` (copies run.yaml, says "provisional" while the budget is provisional).
- `tests/perf/__init__.py`, `tests/perf/.gitignore` (`**/captures/`, `**/raw/`).
- `tests/unit/perf/test_frametimes.py`, `tests/unit/perf/test_compare.py`: 31 tests. Captures are
  generated with a fixed seed inside each test.
- `tests/fixtures/perf/frametimes/presentmon_placeholder_columns.csv`,
  `tests/fixtures/perf/frametimes/capfx_frametime_column.csv`,
  `tests/fixtures/perf/compare/run.yaml`: all marked SYNTHETIC in their first line or header.

## Verification

- `pytest tests/unit/perf -q`: 31 passed.
- `ruff check .`: all checks passed. `ruff format --check .`: 161 files already formatted.
- `mypy`: success, no issues in 73 source files.
- Full `pytest -q`: 1790 passed, 7 skipped, 13 failed. All 13 are in
  `tests/unit/palmscan/test_scan_tree_model.py` and fail with `ModuleNotFoundError: sklearn`
  (the `lidar` extra is not installed in this environment). They are not related to this task.
- `python -m tests.perf.frametimes --help` and `python -m tests.perf.compare --help`: print usage.
- `python scripts/tasks.py validate`: 213 tasks, 0 errors, 0 warnings.
- `git check-ignore`: `tests/perf/runs/<id>/captures/*.csv` and `tests/perf/bakeoff/<date>/raw/*`
  are ignored.

## Decisions and findings

- Spec discrepancy: the plan's prose names `stutter_factor`, `outlier_rel_dev` and
  `stutter_baseline`. The task's YAML nests them as `stutter.factor`, `outliers.rel_dev` and
  `stutter.baseline`. The mapping is one-to-one. I kept the task's nested layout and did not change
  values. Plan not edited.
- Unstable (exit 3) takes precedence over a budget failure (exit 1), because means over unreliable
  runs cannot be trusted. The plan does not state this order; it is recorded here for review.
- A "1% low" definition follows the plan (mean of slowest ceil(N/100) frames). The alternative
  `1000 / p99_frametime_ms` is not reported separately. CapFrameX's definition is still VERIFY (V5).
- Frametime column names, comment prefix and time-column unit are VERIFY (V4, V5). TEST-103 confirms
  them on a real capture and updates `perf_config.yaml`.
- Budget values are the plan's starting values only, marked provisional. No budget number was
  invented.
- The `time_column` option (with `time_unit`) is an assumption: its unit is VERIFY in TEST-103.

## Open issues

- V4, V5 (TEST-103): real PresentMon or CapFrameX column names, comment prefix and CapFrameX 1% low
  definition.
- DEC-005: budget values and `provisional` flag.
- Pre-existing: 13 palmscan tests need the `lidar` extra (scikit-learn). Not in this task's scope.

## Handoff: next steps

1. TEST-103 (sim PC): capture one PresentMon run, check the column names against
   `tests/perf/perf_config.yaml`, set `comment_prefix` and `time_unit`, and compare `avg_fps` and
   `p99_frametime_ms` with the capture tool's summary (within 1%).
2. DEC-005: when the user decides the budget, set `budget.provisional: false` and the values.
3. LIVE-009: write the bake-off run folder as `tests/perf/bakeoff/<date>/` in the plan's run format
   and run `python -m tests.perf.compare tests/perf/bakeoff/<date>`.
