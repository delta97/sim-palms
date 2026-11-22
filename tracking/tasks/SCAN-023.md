---
id: SCAN-023
title: "Peak detection and watershed crown segmentation"
status: in_progress
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w15-peaks-and-crown-segmentation"
depends_on: [SCAN-022]
requires: [none]
agent: lidar-analyst
estimate_h: 3
touches: [palmscan/detect/peaks.py, tests/unit/palmscan/test_scan_peaks.py]
owner: claude-agent
branch: task/scan-023-peak-detection-and-watershed-crown-segme
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-023"
updated: 2026-11-22
---

## Goal

`find_peaks`, `segment_crowns` and `crown_stats` turn a CHM into `LidarCandidate`s with height, crown diameter, height/crown ratio, isolation metric, ground elevation and position.

## Context

- Spec: plan_ref section W15 (steps 1-6 and tests). Thresholds come from `PeakParams` (min height 6 m, min distance 3 m, mask 2 m).
- Height uses the unsmoothed CHM; detection and watershed use the smoothed CHM.
- `shared_boundary_frac` is the isolation metric used by the palm rules (SCAN-024); define it exactly as in the plan.
- Uses `skimage.feature.peak_local_max` and `skimage.segmentation.watershed` (lidar extra).

## Steps

1. `find_peaks(chm, min_height_m, min_distance_m)` with deterministic ordering.
2. `segment_crowns(chm, peaks, mask_height_m)` with markers and mask.
3. `crown_stats(chm, labels, peaks, dataset, tile_id, tile_bounds)`: per-label metrics, lon/lat via `geo.to_wgs84`, `ground_elev_m` via `sample_ground`, `in_building` from the mask, `candidate_id = f"{dataset}:{tile_id}:{n}"`; drop candidates whose peak is in the tile buffer.
4. Tests: two separate cones (diameters within 0.5 m), two cones 2 m apart (one peak), cone in an 8 m plateau (`shared_boundary_frac` > 0.5), isolated cone (< 0.1), buffer-zone peak dropped, ids deterministic.

## Acceptance criteria

- [ ] Synthetic cones give correct count, heights (+/- 0.5 m) and crown diameters (+/- 0.5 m).
- [ ] Embedded vs isolated crowns separate clearly on `shared_boundary_frac`.
- [ ] Peaks in the buffer are dropped.
- [ ] Tests pass offline.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_peaks.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-023-peak-detection-and-watershed-crown-segme worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-023
