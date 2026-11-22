---
id: SCAN-021
title: "Record LiDAR fixtures and confirm 3DEP EPT facts"
status: todo
phase: 4
area: SCAN
kind: test
plan_ref: "plans/detailed/02-detection-pipeline.md#w13-lidar-ept-adapter"
depends_on: [SCAN-020, TEST-100]
requires: [network]
agent: lidar-analyst
estimate_h: 2
touches: [tests/fixtures/palmscan/recorded_lidar/, tests/unit/palmscan/test_scan_recorded_lidar.py, palmscan/sources/lidar_ept.py]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Small real LiDAR clips from test sites T1 (palm street), T2 (beach) and T4 (false positives) are saved as fixtures, and every 3DEP VERIFY item (index URL, properties, naming, SRS, classes, year) is answered and reflected in the adapter.

## Context

- Spec: plan_ref section W13 and the VERIFY table (SCAN-021 rows).
- Site bboxes from TEST-100. Clip each to about 100 m x 100 m around a few known palms (T1), beach palms (T2), and cypress/poles (T4); each LAZ under 3 MB, total under 10 MB.
- Requires PDAL installed locally and network access to the public USGS bucket (no AWS account needed).
- If a VERIFY answer differs from the plan, fix the small parsing functions in `lidar_ept.py` (boundaries properties, year parsing, SRS handling) in this task and note it in the Log.

## Steps

1. Fetch the boundaries index with the adapter; record its URL, property names and one sample feature in `tests/fixtures/palmscan/recorded_lidar/README.md`.
2. For T1, T2, T4: run `select_datasets`, then fetch a 100 m clip with `fetch_tile` (temporary tile size override) into a scratch cache; copy the LAZ files to `tests/fixtures/palmscan/recorded_lidar/<site>.laz`.
3. Inspect each clip (`pdal info --summary`): SRS of the source EPT, classes present (2, 6, 7, 18), point density, return numbers. Record in the README with dataset name and collection year source.
4. Adjust `lidar_ept.py` parsing if needed; rerun SCAN-020 tests.
5. Add `tests/unit/palmscan/test_scan_recorded_lidar.py` (PDAL-optional via `importorskip`): each LAZ reads with `read_points`, has class 2 points, and density > 5 points/m2.

## Acceptance criteria

- [ ] Three LAZ fixtures exist, each < 3 MB, with README metadata (dataset, year, SRS, classes, density).
- [ ] Every SCAN-021 VERIFY row in the plan is answered in the README.
- [ ] SCAN-020 and recorded-LiDAR tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_lidar_ept.py tests/unit/palmscan/test_scan_recorded_lidar.py -q
du -sh tests/fixtures/palmscan/recorded_lidar/*.laz
pdal info --summary tests/fixtures/palmscan/recorded_lidar/t1.laz | head -40
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
