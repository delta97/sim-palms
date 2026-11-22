---
id: TEST-010
title: Build the accuracy metrics script with configurable thresholds
status: in_progress
phase: 4
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#data-accuracy"
depends_on: [TEST-009]
requires: [none]
agent: test-engineer
estimate_h: 4
touches: [tests/accuracy/metrics.py, tests/accuracy/thresholds.yaml, tests/unit/accuracy/test_metrics.py, tests/fixtures/accuracy/metrics/]
owner: claude-agent
branch: task/test-010-build-the-accuracy-metrics-script-with-c
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-010"
updated: 2026-11-22
---

## Goal

`python -m tests.accuracy.metrics evaluate` computes precision, recall, position error, height error and species accuracy of a `palms.geojson` against a site's ground truth, using one-to-one matching within a configurable radius, and checks the plan's starting targets from `thresholds.yaml`.

## Context

- Spec: `plans/detailed/06-testing.md#matching-algorithm`, `#metric-definitions`, `#thresholds`. Follow the formulas exactly.
- Ground-truth loaders come from `tests/accuracy/gt.py` (TEST-009).
- Uses numpy, scipy (`linear_sum_assignment`), shapely, pyproj.
- This is the single implementation of matching, metrics and thresholds, and the one that gates Phase 4 (TEST-012). SCAN-029 imports `evaluate`, `load_thresholds` and `check_thresholds` from here for palmscan's in-run QA, so keep those signatures stable and documented; never duplicate them in `palmscan`.
- Predictions normally come from the canonical palmscan output `build/scan/<region>/palms.geojson`.
- Thresholds live only in `tests/accuracy/thresholds.yaml` (and per-site `meta.yaml` overrides). No hard-coded targets in Python.

## Steps

1. `tests/accuracy/thresholds.yaml`: copy the YAML block from the plan.
2. `tests/accuracy/metrics.py`:
   - `match(pred_xy, gt_xy, radius_m) -> list[tuple[int, int, float]]` (indices + distance), implementing steps 4-5 of the matching algorithm.
   - `evaluate(pred_fc, gt_fc, area, *, radius_m, profile) -> dict` returning counts (TP, FP, FN, ignored), precision, recall, f1, position error stats, height error stats (n, median, mean, p90, bias), height-class agreement, species accuracy + confusion matrix + split by `species_source`, and the lists of FP/FN feature ids.
   - `check_thresholds(result, thresholds) -> list[str]` (failures; `null` thresholds skipped and reported as "not checked").
   - `load_thresholds(site, path=None, overrides=None)` with precedence CLI > site meta > file.
   - CLI `evaluate --site <T> --pred <palms.geojson> [--profile <name>] [--all-profiles] [--radius <m>] [--label <x>] [--write]`. Print a compact Markdown summary. `--write` saves `tests/accuracy/<site>/results/<date>_<label>_<profile>.json`, `.md`, and `_errors.geojson` (FP and FN points, property `error: fp|fn`, plus `gt_id` or `palm_id`). Exit 0 / 1 / 2 as in the plan.
3. Fixtures `tests/fixtures/accuracy/metrics/`: a 6-point GT row (8 m spacing), its area, and prediction files: exact copy, shifted 2.5 m north, shifted 3.5 m north, one missing + one extra, and a "greedy trap" case (two rows offset so greedy nearest-first gives a wrong pairing).
4. `tests/unit/accuracy/test_metrics.py`, covering the properties in `plans/detailed/06-testing.md#verification-strategy`: exact copy gives P = R = 1 and zero error; 2.5 m shift gives P = R = 1 and median 2.5 (±0.05); 3.5 m shift gives P = R = 0; missing+extra gives P = R = 5/6; greedy trap gives all matches; a low-confidence GT point unmatched is ignored, not FN; a prediction outside the area is ignored; profile filters by `detected_by` and `context` work; height error uses only non-null `height_ref_m`; species accuracy ignores `unknown`; a threshold override in meta wins over the file; `null` thresholds never fail.

## Acceptance criteria

- [ ] Metrics match the formulas in the plan; all tests pass.
- [ ] Every target is read from `thresholds.yaml` (grep finds no numeric target in `metrics.py` other than defaults for CLI parsing).
- [ ] `--write` produces the three result files.
- [ ] Exit codes as specified.

## Verification

```bash
pytest tests/unit/accuracy/test_metrics.py -q
python -m tests.accuracy.metrics evaluate --help
grep -nE "0\.9|0\.8|2\.0" tests/accuracy/metrics.py   # expect no threshold literals
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Confirmed as the single accuracy-metrics implementation and the one that gates Phase 4: SCAN-029 now calls this module's evaluate/load_thresholds/check_thresholds instead of reimplementing them, so those functions are a public API. Example --pred path is the canonical build/scan/<region>/palms.geojson. Cross-area reconciliation.
- 2026-11-22 [integrator] integrator note from TEST-009: import height classes from gt.height_class (S<8, M 8-<15, T 15-<25, X>=25). GT species check is pattern-only; palmscan/data/species_keys.yaml is now on main (SCAN-002) and can be used for a registry check
- 2026-11-22 [claude-agent] Claimed. branch=task/test-010-build-the-accuracy-metrics-script-with-c worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-010
