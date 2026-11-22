---
id: TEST-013
title: Build the frametime capture parser and run comparison report
status: todo
phase: 5
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#frametime-metrics"
depends_on: [TEST-001]
requires: [none]
agent: test-engineer
estimate_h: 5
touches: [tests/perf/__init__.py, tests/perf/frametimes.py, tests/perf/compare.py, tests/perf/perf_config.yaml, tests/perf/.gitignore, tests/unit/perf/test_frametimes.py, tests/unit/perf/test_compare.py, tests/fixtures/perf/frametimes/, tests/fixtures/perf/compare/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Given frametime captures from PresentMon or CapFrameX, compute avg FPS, 1% low, p99 frametime and stutter count per capture, then compare no-fix / static / live runs against the budget and write a report. This decides the Phase 5 bake-off with numbers.

## Context

- Spec: `plans/detailed/06-testing.md#frametime-metrics`, `#run-comparison`, `#perf-capture-format`. Use the formulas exactly.
- Real capture column names are unknown (VERIFY V4, V5). Make the column configurable and use the placeholder list from the plan. TEST-103 confirms real names with a real capture and updates `perf_config.yaml`. Don't claim the placeholders are correct.
- Users: TEST-103 (dry run), LIVE-009 (the Phase 5 bake-off, run folders under `tests/perf/bakeoff/<date>/`), GATE-P6 per-region checks. `compare` must accept any run dir in the plan's format.
- Budget values are DEC-005's decision. Ship the plan's starting values (5% frametime, no added stutter) marked `provisional: true`.

## Steps

1. `tests/perf/perf_config.yaml`:
   ```yaml
   capture:
     frametime_columns: [MsBetweenPresents, FrameTime, msBetweenPresents]   # VERIFY in TEST-103
     time_column: null          # optional; if null, time = cumulative frametime
     comment_prefix: "//"       # lines to skip, VERIFY
     trim_start_s: 5
     trim_end_s: 0
   stutter: {factor: 2.0, baseline: global, rolling_window_s: 30}
   outliers: {rel_dev: 0.10, min_kept: 2}
   budget:
     provisional: true          # set false when DEC-005 is decided
     frametime_pct_max: 5.0
     stutter_abs_tol: 3
     stutter_rel_tol: 0.10
     low1_drop_pct_max: null
   ```
2. `tests/perf/frametimes.py`: `read_frametimes(path, config) -> numpy array (ms)` (CSV; skip comment lines; first matching column; drop non-numeric and ≤ 0 rows with a count in the result); `trim(...)`; `compute_metrics(ft_ms, config) -> dict` with every metric in the plan table, plus `n_frames`, `n_dropped_rows`. CLI `python -m tests.perf.frametimes <capture.csv>` prints the metrics as JSON.
3. `tests/perf/compare.py`: `python -m tests.perf.compare <run_dir> [--captures <dir>] [--config <yaml>]`. Find `<variant>_r<n>.csv` in `<run_dir>/captures/` (or `--captures`), compute metrics, write `metrics.json`, apply the outlier rule, average kept runs, compute deltas vs `nofix`, check the budget, write `report.md` and `report.json`. Exit 0 / 1 / 2 / 3 as in the plan. The report header copies `run.yaml` (hardware, settings, versions) and says "budget provisional" while `provisional: true`.
4. `tests/perf/.gitignore`: `**/captures/` and `**/raw/` (covers `runs/`, LIVE-009's `bakeoff/` and LIVE-101's `soak/`).
5. Tests (`tests/unit/perf/`):
   - `compute_metrics` on constant 16.667 ms × 3000 frames: avg_fps 60.0 (±0.01), stutter 0, p99 16.667.
   - 99 frames of 10 ms + 1 frame of 50 ms: `avg_frametime_ms` 10.4; `stutter_count` 1; `low1_fps` 20.0; p99 by numpy linear method (compute expected in the test with numpy).
   - Trim removes the first 5 s.
   - CSV fixture in `tests/fixtures/perf/frametimes/` with a comment line, extra columns and a non-numeric row; second fixture using the second placeholder column name.
   - `compare` with fixture runs in `tests/fixtures/perf/compare/`: (a) static 3% slower, passes; (b) static 6% slower, exit 1; (c) one planted outlier dropped and noted; (d) two outliers, exit 3; (e) missing `nofix`, exit 2. Generate the CSVs in the test (numpy, fixed seed) rather than committing large files.

## Acceptance criteria

- [ ] Metrics follow the plan formulas; tests pass.
- [ ] Column names, trim, stutter, outlier and budget values all come from `perf_config.yaml`.
- [ ] Report says "provisional" until DEC-005 sets `provisional: false`.
- [ ] Raw captures are gitignored.

## Verification

```bash
pytest tests/unit/perf -q
python -m tests.perf.frametimes --help
python -m tests.perf.compare --help
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
