---
id: SCAN-030
title: "Tune LiDAR palm thresholds on test sites"
status: todo
phase: 4
area: SCAN
kind: test
plan_ref: "plans/detailed/02-detection-pipeline.md#w21-threshold-tuning-and-phase-4-deliverable"
depends_on: [SCAN-021, SCAN-028, TEST-101]
requires: [network, human]
agent: lidar-analyst
estimate_h: 4
touches: [palmscan/config.py, tests/unit/palmscan/test_scan_config.py, tracking/logs/SCAN-030-tuning.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

LiDAR detection thresholds are tuned on real data at T1, T2 and T4 so LiDAR-only detection reaches the starting targets (precision >= 90%, recall >= 80%) or the gap is documented, and the chosen values become the defaults.

## Context

- Spec: plan_ref section W21, tuning procedure steps 1-5.
- Ground truth from TEST-101 (two sites); false-positive site T4 from TEST-100 (Italian cypress, eucalyptus, light poles).
- Decide plan Q1 (large-crown ratio exemption) with data here.
- Region-specific overrides belong in region YAMLs (REGION area), not in this task.

## Steps

1. Run `palmscan run -vv --only lidar` on bboxes covering T1, T2, T4 (via the test region YAMLs or temporary copies outside `regions/`).
2. `palmscan eval --palms build/scan/<region>/palms.geojson --site <T>` per labeled site (TEST-010 metrics via SCAN-029); record baseline P/R/position/height in `tracking/logs/SCAN-030-tuning.md`.
3. Review `qa_rejects.csv` and `lidar_candidates` over imagery in QGIS; for each rule count true palms rejected and non-palms accepted.
4. Change one threshold at a time (peaks min distance, ratio, shared boundary, crown bounds, exemption); rerun offline from cache; log each run.
5. Set the final values as defaults in `palmscan/config.py`; update `test_scan_config.py` default assertions; note the Q1 decision.

## Acceptance criteria

- [ ] Tuning log lists baseline and every trial with params and metrics.
- [ ] Final LiDAR-only metrics for both labeled sites recorded, with pass/fail vs targets.
- [ ] New defaults in `palmscan/config.py`; all unit tests pass.
- [ ] Q1 decision recorded in the log.

## Verification

```bash
palmscan run --region <t2-region> --only lidar --offline --eval-site T2 && cat build/scan/<t2-region>/accuracy.json
pytest tests/unit/palmscan -q
```
Manual: reviewer reads `tracking/logs/SCAN-030-tuning.md` and spot-checks 10 accepted and 10 rejected candidates in QGIS.

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Evaluation commands use --eval-site / eval --site (TEST-010 via SCAN-029) instead of --truth. Cross-area reconciliation.
