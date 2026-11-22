---
id: TEST-012
title: Evaluate Phase 4 palmscan output against ground truth at T1, T2 and T4
status: todo
phase: 4
area: TEST
kind: test
plan_ref: "plans/detailed/06-testing.md#data-accuracy"
depends_on: [TEST-010, TEST-101, TEST-011, SCAN-101]
requires: [network]
agent: test-engineer
estimate_h: 2
touches: [tests/accuracy/T1/, tests/accuracy/T2/, tests/accuracy/T4/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Committed accuracy results for the Phase 4 (LiDAR-enriched) palmscan output at T1, T2 and T4, with a pass/fail line per Phase 4 target. GATE-P4 reads these.

## Context

- Metrics and thresholds: `plans/detailed/06-testing.md#data-accuracy`; tool from TEST-010.
- Phase 4 targets: `lidar_only` precision ≥ 0.90 and recall ≥ 0.80; median height error < 2 m; position error median < 2 m. `combined` recall ≥ 0.90 reported.
- `requires: network` because palmscan pulls LiDAR (EPT on S3). If the palmscan output already exists locally, the evaluation itself needs no network.
- VERIFY (V15): palmscan output paths (`palms.geojson`, CHM GeoTIFF). Check `plans/detailed/02-detection-pipeline.md` and SCAN-101.

## Steps

1. Run (or locate) the Phase 4 palmscan output for the region(s) containing T1, T2, T4: `palmscan run --region <r>` per SCAN-101.
2. If `height_ref_m` is still null: `python -m tests.accuracy.gt fill-heights <T> --chm <chm.tif>` for T1 and T2; commit the updated ground truth.
3. For T1, T2, T4: `python -m tests.accuracy.metrics evaluate --site <T> --pred <palms.geojson> --all-profiles --label phase4 --write`.
4. Open each `_errors.geojson` in QGIS over the imagery. For each FP and FN, decide: detector error, or label error. Fix label errors in the ground truth (log each fix with its `gt_id`), then rerun step 3.
5. Write a short summary in the Log: per site and profile, precision, recall, position median, height median, species accuracy, pass/fail. Note the main FP causes (cypress, poles, etc.) for SCAN.

## Acceptance criteria

- [ ] Results files for T1, T2, T4 committed under `tests/accuracy/<T>/results/`.
- [ ] Summary of every Phase 4 target with pass/fail in the Log.
- [ ] Label fixes, if any, logged by `gt_id`.

## Verification

```bash
ls tests/accuracy/T1/results/ tests/accuracy/T2/results/ tests/accuracy/T4/results/
python -m tests.accuracy.metrics evaluate --site T1 --pred <palms.geojson> --profile lidar_only; echo "exit=$?"   # 0 = targets met
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
