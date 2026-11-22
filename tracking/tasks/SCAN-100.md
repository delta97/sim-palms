---
id: SCAN-100
title: "Deliverable: palmscan run produces validated palms.geojson from inventory data (Phase 1)"
status: todo
phase: 1
area: SCAN
kind: test
plan_ref: "plans/detailed/02-detection-pipeline.md#w12-phase-1-deliverable-run"
depends_on: [SCAN-007, SCAN-013, TEST-100]
requires: [network, human]
agent: geo-data-engineer
estimate_h: 2
touches: [tracking/logs/SCAN-100-run.md, palmscan/data/species_aliases.csv]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`palmscan run --region <test>` works end to end on live inventory data for the Phase 0/1 test block, and a human check of the QA map shows at least 90% of palms visible along inventory streets have a point within 3 m (Phase 1 exit criterion).

## Context

- Spec: plan_ref section W12; exit criterion in `plans/05-phases.md` Phase 1.
- Test block from DEC-004 and site T1 from TEST-100. The region YAML must already exist under `regions/` (REGION/ARCH own it; plan Q7). If it is missing, set this task to `blocked` with a note instead of creating it.
- Needs QGIS (or any GIS that opens GeoPackage) with a public aerial basemap. This is the anchor other areas (GEN-100, GATE-P1) depend on.

## Steps

1. Confirm `regions/<test>.yaml` exists and loads: `python -c "from palmscan.config import load_scan_config as l; print(l('<test>'))"`.
2. `palmscan run --region <test> -v`. Fix only data-table issues here (aliases); code bugs go to a new task.
3. Rerun with `--offline`; `cmp` the two `palms.geojson` files.
4. Open `build/scan/<test>/qa_map.gpkg` in QGIS over aerial imagery. On at least three inventory streets inside T1, count visible palms (target 50+) and those with a `palms` point inside the `check_radius_3m` layer.
5. Note misses with a likely cause (not in inventory, stale record, name not normalized, filtered by mistake). Add missed names to `palmscan/data/species_aliases.csv` and rerun if needed.
6. Write `tracking/logs/SCAN-100-run.md`: date, region, command, palmscan version/git sha, counts from `qa_summary.md`, visual check counts and percentage, misses, follow-ups.

## Acceptance criteria

- [ ] Live run exits 0; `palms.geojson` validates against the ARCH-002 schema.
- [ ] Offline rerun is byte-identical.
- [ ] Visual check: >= 90% of counted palms have a point within 3 m; counts recorded in the run log.
- [ ] Run log committed at `tracking/logs/SCAN-100-run.md`.

## Verification

```bash
palmscan run --region <test> -v && cp build/scan/<test>/palms.geojson /tmp/p1.geojson
palmscan run --region <test> --offline && cmp /tmp/p1.geojson build/scan/<test>/palms.geojson && echo identical
```
Manual: QGIS procedure in Steps 4-5; reviewer checks the counts in `tracking/logs/SCAN-100-run.md`.

## Log

- 2026-11-21 [plan-breakdown] Task created.
