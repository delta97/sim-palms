---
id: SCAN-025
title: "Inventory-to-LiDAR matching and merge"
status: review
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w17-inventory-lidar-merge"
depends_on: [SCAN-008]
requires: [none]
agent: lidar-analyst
estimate_h: 3
touches: [palmscan/detect/merge.py, tests/unit/palmscan/test_scan_merge.py]
owner: claude-agent
branch: task/scan-025-inventory-to-lidar-matching-and-merge
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-025"
updated: 2026-11-22
---

## Goal

`merge()` matches inventory palms to LiDAR candidates one-to-one within 3 m, copies LiDAR height/crown/ground to matches, adds LiDAR-only palms, computes per-species region median heights, and returns labeled pairs for training the species classifier.

## Context

- Spec: plan_ref section W17 (steps 1-7) and source plan section 4.
- Rule-rejected candidates still match inventory palms unless the rejection includes `building`.
- Inventory position is kept for matched palms (plan Q8).
- Uses `PalmRecord`/`LidarCandidate` from `palmscan/model.py`; candidates in tests are built by hand (no dependency on the peaks code).

## Steps

1. `match_inventory_to_lidar(inv, cands, match_radius_m)` with `cKDTree.query_ball_point` and global greedy assignment sorted by (distance, stable_key, candidate_id).
2. `merge(inv, cands, params, dedupe_radius_m)`: apply matches (height_source `lidar`, `detected_by` `inventory+lidar` / `osm+lidar`, `source_ids` + `lidar:<candidate_id>`, `data_vintage["lidar"]`), build LiDAR-only palms from accepted unmatched candidates not within 2 m of an inventory palm (else reject `near_inventory`), compute `region_medians` (min n = `region_median_min_n`), collect `training`.
3. LiDAR-only stable key `lidar:<dataset>:<round(x)>:<round(y)>`.
4. Tests from W17.

## Acceptance criteria

- [x] Matching is one-to-one and deterministic under input shuffling.
- [x] Match at 2.9 m, none at 3.1 m.
- [x] Building-rejected candidates never match; other rule-rejected candidates can.
- [x] Region medians omitted for species with fewer than 5 matches.
- [x] Tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_merge.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-025-inventory-to-lidar-matching-and-merge worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-025
- 2026-11-22 [claude-agent] Added palmscan/detect/merge.py (match_inventory_to_lidar, merge, MergeResult) and 15 tests in test_scan_merge.py: one-to-one, order-independent (shuffle test), 2.9 m match / 3.1 m none, building-rejected never matches, other rejects match, region medians omitted below 5. Full suite 1646 passed, ruff and mypy clean. Plan fix: W17 source_ids row said lidar:<dataset>:<candidate id> but candidate_id already starts with the dataset; now lidar:<candidate id> as in W17 step 3. Added optional min_height_m kwarg to merge (default PeakParams.min_height_m) since MergeParams has no height floor.
- 2026-11-22 [claude-agent] Status in_progress -> review.
