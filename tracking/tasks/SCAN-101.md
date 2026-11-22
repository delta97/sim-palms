---
id: SCAN-101
title: "Deliverable: LiDAR-enriched palmscan run with heights and LiDAR-only palms (Phase 4)"
status: todo
phase: 4
area: SCAN
kind: test
plan_ref: "plans/detailed/02-detection-pipeline.md#w21-threshold-tuning-and-phase-4-deliverable"
depends_on: [SCAN-030, SCAN-100]
requires: [network, human]
agent: lidar-analyst
estimate_h: 3
touches: [tracking/logs/SCAN-101-run.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

LiDAR-enriched `palms.geojson` exists for the Phase 1 test region and the beach site, with measured heights on matched palms, LiDAR-only palms where inventories have none, and an accuracy report against the Phase 4 targets. GEN and GATE-P4 build on this.

## Context

- Spec: plan_ref section W21 (deliverable paragraph) and `plans/05-phases.md` Phase 4 exit criteria.
- Uses the thresholds from SCAN-030. Accuracy numbers come from TEST-010's evaluator (via SCAN-029); the gating Phase 4 evaluation is TEST-012, which reads this task's `build/scan/<region>/palms.geojson`. The in-sim beach check needs a palmgen build and belongs to GATE-P4, not here.
- Targets: LiDAR-only precision >= 90%, recall >= 80%; median height error < 2 m on matched palms (reported as defined in plan Q9).

## Steps

1. `palmscan run --region <test> --eval-site T1` and the same for the beach region with `--eval-site T2`.
1a. Record the vertical datum of the EPT dataset(s) used and confirm `ground_elev_m` is orthometric metres (ARCH-002 `VERIFY:`); note it in the run log.
2. Also run `--only lidar` for both to get LiDAR-only precision/recall.
3. Rerun all four with `--offline`; confirm byte-identical `palms.geojson`.
4. Open both `qa_map.gpkg` files in QGIS; spot-check 20 LiDAR-only palms over imagery.
5. Write `tracking/logs/SCAN-101-run.md`: commands, versions, counts by `detected_by`, share with LiDAR height, classifier report (tree used or not), accuracy tables with pass/fail, spot-check result, open issues.

## Acceptance criteria

- [ ] Both regions produce schema-valid `palms.geojson` with `height_source=lidar` on matched palms.
- [ ] Beach region contains `detected_by=lidar` palms.
- [ ] Accuracy for both labeled sites recorded with pass/fail; failures have a follow-up note.
- [ ] Offline reruns byte-identical.

## Verification

```bash
palmscan run --region <test> --eval-site T1 && cat build/scan/<test>/accuracy.json
palmscan run --region <beach> --only lidar --eval-site T2 && cat build/scan/<beach>/accuracy.json
```
Manual: reviewer checks `tracking/logs/SCAN-101-run.md` against the Phase 4 targets.

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Accuracy runs via --eval-site (TEST-010 metrics through SCAN-029); TEST-012 is the gating Phase 4 evaluation, this task records palmscan's in-run numbers. Added the ground_elev_m vertical-datum VERIFY (ARCH-002). Cross-area reconciliation.
