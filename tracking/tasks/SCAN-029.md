---
id: SCAN-029
title: Run the TEST-010 accuracy evaluation from palmscan (in-run QA)
status: done
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w19-accuracy-metrics"
depends_on: [SCAN-001, TEST-010]
requires: [none]
agent: test-engineer
estimate_h: 2
touches: [palmscan/qa/accuracy.py, tests/unit/palmscan/test_scan_accuracy.py, tests/fixtures/palmscan/accuracy/]
owner: claude-agent
branch: task/scan-029-run-the-test-010-accuracy-evaluation-fro
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-029"
updated: 2026-11-22
---

## Goal

`palmscan/qa/accuracy.py` runs the TEST-010 evaluator (`tests/accuracy/metrics.py`) on a palmscan run's output for a labeled test site, writes `accuracy.json` and the Accuracy section of `qa_summary.md`, and adds the SCAN-only fallback height error. It does not implement matching or metrics itself: TEST-010 is the single implementation and is what gates Phase 4 (TEST-012).

## Context

- Spec: plan_ref section W19 (rescoped 2026-11-22).
- Ground truth format and loaders: TEST-009 (`tests/accuracy/<site>/ground_truth.geojson`, `labeled_area.geojson`, `meta.yaml`; `tests/accuracy/gt.py`). Height classes are TEST's: `S` < 8 m, `M` 8 to < 15, `T` 15 to < 25, `X` >= 25, `unknown`.
- Metrics, profiles (`lidar_only`, `combined`, `phase1_inventory`) and targets: TEST-010 (`tests.accuracy.metrics.evaluate`, `load_thresholds`, `check_thresholds`, `tests/accuracy/thresholds.yaml`). Never copy targets or formulas into palmscan.
- `tests/` is not part of the wheel, so the evaluator is importable only from a repo checkout: import it with the repo root on `sys.path`; if that fails, log a QA warning ("accuracy skipped: tests.accuracy not importable") and continue.

## Steps

1. `load_evaluator(repo_root) -> module | None` (imports `tests.accuracy.metrics` and `tests.accuracy.gt`).
2. `evaluate_site(palms_fc, site, *, repo_root, sites_root=None, profiles=None, radius_m=None) -> dict[str, dict]`: load the site's ground truth and area with TEST-009's loaders (`sites_root` defaults to `tests/accuracy`), then per profile call TEST-010's `load_thresholds`, `evaluate` and `check_thresholds`; return the results unchanged plus the failure list.
3. `fallback_height_error(palms) -> float | None` (SCAN-only, W19), added to the result as `fallback_height_error_m`.
4. `write_accuracy(results, out_dir)` -> `accuracy.json`; `accuracy_section_md(results)` for `qa_summary.md` (per profile: P, R, position and height error, pass/fail as reported by TEST-010).
5. Fixtures in `tests/fixtures/palmscan/accuracy/`: `pred.geojson` and a tiny site folder `site_TX/` (`ground_truth.geojson`, `labeled_area.geojson`, `meta.yaml`) in the TEST-009 format, `README.md`.
6. Tests: `evaluate_site` on the fixture returns exactly what calling TEST-010's `evaluate` directly returns; profiles pass through; missing evaluator -> warning, no crash; `fallback_height_error` on a hand-built set; empty predictions do not raise.

## Acceptance criteria

- [x] No matching or metric formula and no numeric target is defined in `palmscan/qa/accuracy.py` (grep for `linear_sum_assignment` and `0.9` finds nothing).
- [x] `evaluate_site` results equal TEST-010's `evaluate` output on the fixture.
- [x] Empty prediction set does not raise; missing evaluator is a warning.
- [x] Tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_accuracy.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Rescoped: TEST-010 is the single accuracy-metrics implementation and the one that gates Phase 4. This task no longer reimplements matching/metrics; it loads the site ground truth through TEST-009/TEST-010, runs TEST-010's evaluate/check_thresholds for palmscan's in-run QA, and keeps only the SCAN-specific fallback height error. Height classes follow TEST (S/M/T/X, edges 8/15/25 m). Added depends_on TEST-010. Cross-area reconciliation.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-029-run-the-test-010-accuracy-evaluation-fro worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-029
- 2026-11-22 [claude-agent] Built palmscan/qa/accuracy.py on TEST-010 (metrics.evaluate, load_thresholds, profile_for, check_thresholds, unchecked_thresholds) and TEST-009 (gt.load_ground_truth, load_labeled_area). No matching or metric code; grep for linear_sum_assignment and 0.9 finds nothing (also asserted in a test).
- 2026-11-22 [claude-agent] AC2: evaluate_site results equal direct TEST-010 evaluate and check_thresholds on fixture T9 for all three profiles (test_evaluate_site_equals_direct_test010_call).
- 2026-11-22 [claude-agent] AC3: empty predictions (pred_empty.geojson) do not raise; precision None, recall 0.0, undefined-precision failure reported. Missing evaluator (repo_root outside checkout) gives warning 'accuracy skipped: tests.accuracy not importable' and {} (no crash).
- 2026-11-22 [claude-agent] Deviation: site folder is T9, not site_TX. TEST-009 site ids must match T[0-9]+ (gt.site_dir); the fixture root is tests/fixtures/palmscan/accuracy/ with sites_root passed in.
- 2026-11-22 [claude-agent] Deviation: load_evaluator returns a Evaluator(metrics, gt) namedtuple (or None) instead of a bare module, since both TEST modules are used. It also refuses a tests package that resolves outside repo_root.
- 2026-11-22 [claude-agent] Verification: pytest tests/unit/palmscan/test_scan_accuracy.py -q -> 10 passed. Full: pytest -q -> 1587 passed, 1 skipped; ruff check clean; ruff format --check 141 files formatted; mypy 66 files no issues.
- 2026-11-22 [claude-agent] Commit f2934ca scan(SCAN-029): run TEST-010 accuracy evaluation from palmscan QA.
- 2026-11-22 [claude-agent] Status in_progress -> review.
- 2026-11-22 [integrator] Status review -> done.
