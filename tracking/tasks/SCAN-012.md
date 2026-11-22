---
id: SCAN-012
title: "QA outputs: qa_summary.md, qa_map.gpkg, qa_rejects.csv"
status: in_progress
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w10-qa-outputs"
depends_on: [SCAN-001]
requires: [none]
agent: geo-data-engineer
estimate_h: 3
touches: [palmscan/qa/summary.py, palmscan/qa/gpkg.py, palmscan/qa/rejects.py, tests/unit/palmscan/test_scan_qa.py, tests/fixtures/palmscan/qa/]
owner: claude-agent
branch: task/scan-012-qa-outputs-qa-summary-md-qa-map-gpkg-qa
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-012"
updated: 2026-11-22
---

## Goal

Every run can write the three QA files from the source plan: a readable Markdown summary, a GeoPackage for QGIS review over aerial imagery, and a CSV of every reject with its reason.

## Context

- Spec: plan_ref section W10 (column order, layer list, vintage grid, summary sections 1-12).
- Write the Phase 4 layers and sections (`lidar_candidates`, `crowns`, Classifier, Accuracy) as optional inputs now: empty/omitted when not provided. SCAN-028 fills them.
- Inputs are model dataclasses from `palmscan/model.py`, so this task does not depend on the adapters.

## Steps

1. `palmscan/qa/rejects.py`: `write_rejects_csv(rejects, path)` with the exact column order and sorting.
2. `palmscan/qa/gpkg.py`: `vintage_grid(palms, step_deg, run_year, stale_years) -> GeoDataFrame` with `cell_id` like `n32p78_w117p26`; `write_qa_gpkg(path, palms, rejects, conflict_buildings, vintage_grid, candidates=None, crowns=None)` writing all layers (empty layers keep their schema); buffers built in local CRS.
3. `palmscan/qa/summary.py`: `QaContext` dataclass and `render_summary(ctx) -> str`, `write_summary(ctx, path)`; sections in plan order; git sha via `git rev-parse --short HEAD` with failure tolerated.
4. Fixtures: `tests/fixtures/palmscan/qa/expected_summary.md` generated from a fixed `QaContext` (timestamp line masked in comparison).
5. Tests: CSV header and order; GPKG layer names via `pyogrio.list_layers`; `check_radius_3m` polygon area ~ 28.3 m2; vintage grid stale flag; summary golden comparison; optional sections absent when no data.

## Acceptance criteria

- [ ] `qa_map.gpkg` contains layers `palms`, `exclusion_circles`, `check_radius_3m`, `rejects`, `building_conflicts`, `vintage_grid` (plus Phase 4 layers when given).
- [ ] `qa_rejects.csv` columns match the plan exactly.
- [ ] Summary golden test passes with the timestamp masked.
- [ ] Tests pass offline.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_qa.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-012-qa-outputs-qa-summary-md-qa-map-gpkg-qa worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-012
