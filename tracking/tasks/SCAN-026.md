---
id: SCAN-026
title: "Species shape rules and classification order"
status: review
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w18-species-classification"
depends_on: [SCAN-010]
requires: [none]
agent: lidar-analyst
estimate_h: 2
touches: [palmscan/classify/species.py, tests/unit/palmscan/test_scan_species_rules.py]
owner: claude-agent
branch: task/scan-026-species-shape-rules-and-classification-o
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-026"
updated: 2026-11-22
---

## Goal

`classify()` assigns species to every palm in the source plan's order (inventory/OSM name, then a shape model if given, then LiDAR shape rules, then regional priors), with the plan's confidence values and `species_source` labels.

## Context

- Spec: plan_ref section W18, `species.py` part, and source plan section 5.
- `ShapeModel` protocol is defined here; SCAN-027 implements it without editing this file.
- Rules never output `washingtonia_filifera`. Priors sampling comes from `palmscan/classify/priors.py` (SCAN-010).

## Steps

1. `FEATURES`, `ShapeModel` protocol, `features_of(palm) -> np.ndarray`.
2. `shape_rules(height_m, crown_diam_m)` with inclusive bounds, rule order as listed.
3. `classify(palms, priors, model=None)` in the four-step order; updates `species`, `species_confidence`, `species_source` in place.
4. Tests: each rule boundary (e.g. 18.0/5.0 robusta, 17.9 not), overlap 10 m/7 m -> canariensis, fallback to priors with confidence 0.3, inventory species untouched, a fake `ShapeModel` returning `None` falls through to rules.

## Acceptance criteria

- [x] Boundary tests pass for all three rules.
- [x] Inventory/OSM species are never overwritten.
- [x] A model answer sets `species_source="lidar_tree"`; rules set `lidar_rules`; priors set `prior`.
- [x] Tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_species_rules.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-026-species-shape-rules-and-classification-o worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-026
- 2026-11-22 [claude-agent] All 4 acceptance criteria pass: tests/unit/palmscan/test_scan_species_rules.py 29 tests; full suite 1602 passed 5 skipped; ruff check/format and mypy clean. Rule table is data (DEFAULT_SHAPE_RULES, marked VERIFY: assets/reference has no species ranges). Plan W18 updated with optional rules param.
- 2026-11-22 [claude-agent] Status in_progress -> review.
