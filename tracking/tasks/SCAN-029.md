---
id: SCAN-029
title: "Accuracy metrics against ground truth"
status: todo
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w19-accuracy-metrics"
depends_on: [SCAN-001]
requires: [none]
agent: test-engineer
estimate_h: 2
touches: [palmscan/qa/accuracy.py, tests/unit/palmscan/test_scan_accuracy.py, tests/fixtures/palmscan/accuracy/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`palmscan/qa/accuracy.py` computes precision, recall, F1, position error, height and species agreement for a `palms.geojson` against hand-labeled ground truth, and reports pass/fail against the targets in `plans/06-testing.md`.

## Context

- Spec: plan_ref section W19.
- Ground truth is produced by TEST-101. Its file format is not fixed yet; the assumed format is in W19. Keep format handling in one `load_truth(path) -> GeoDataFrame` function so it can adapt without touching metric code.
- Targets: precision >= 0.90; recall >= 0.80 LiDAR-only and >= 0.90 with inventory; median position error < 2 m; median height error < 2 m.

## Steps

1. `load_truth(path)`, `AccuracyReport`, `evaluate(palms, truth, area=None, match_radius_m=3.0)`, `fallback_height_error(palms)`, `targets_table(report, mode)` where mode is `lidar_only` or `with_inventory`.
2. Matching: one-to-one greedy by distance in local CRS.
3. Metrics with `None` for undefined values (empty sets).
4. Fixtures in `tests/fixtures/palmscan/accuracy/`: `truth.geojson` (10 points with height_class and species), `pred.geojson` (7 TP, 2 FP, 3 FN by construction), `README.md`.
5. Tests: exact TP/FP/FN, precision 7/9, recall 7/10, median position error, height class agreement, species accuracy, empty predictions, evaluation area filtering.

## Acceptance criteria

- [ ] Fixture metrics match the hand-computed values exactly.
- [ ] Empty prediction set returns `None` precision without raising.
- [ ] Targets table marks pass/fail per metric.
- [ ] Tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_accuracy.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
