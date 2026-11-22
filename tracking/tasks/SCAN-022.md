---
id: SCAN-022
title: "Canopy height model (DTM, DSM, CHM)"
status: review
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w14-canopy-height-model"
depends_on: [SCAN-001]
requires: [none]
agent: lidar-analyst
estimate_h: 3
touches: [palmscan/detect/chm.py, tests/unit/palmscan/test_scan_chm.py, pyproject.toml]
owner: claude-agent
branch: task/scan-022-canopy-height-model-dtm-dsm-chm
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-022"
updated: 2026-11-22
---

## Goal

`build_chm()` turns a structured point array into DTM, DSM, CHM and smoothed CHM rasters at 0.5 m, plus an optional building mask, and `sample_ground()` returns ground elevation at given points.

## Context

- Spec: plan_ref section W14 (steps 1-6, performance target, test cases) and source plan section 3.
- Input array fields: `X Y Z Classification ReturnNumber NumberOfReturns` in local metric CRS (see `read_points` in SCAN-020; this task does not import it).
- Pure numpy/scipy; `rasterio` only for `write_debug_rasters` (import inside the function so the module works without it).

## Steps

1. `ChmResult` dataclass; grid snapping helper.
2. DTM: class 2 per-cell mean via `np.bincount`; fill with `griddata(linear)` then nearest; no ground -> `SourceError`.
3. DSM: first returns per-cell max; single 3x3 max-filter pass for holes; remaining holes = DTM.
4. CHM = DSM - DTM, negatives -> 0, > 60 m -> 0 (count outliers in `ChmResult.outliers`).
5. `chm_smooth` with `scipy.ndimage.gaussian_filter`.
6. Building mask from class 6 top returns when present, else `None`.
7. `sample_ground(chm, x, y)` bilinear on the DTM; `write_debug_rasters` GeoTIFFs.
8. Synthetic point generator helper inside the test module (flat or sloped ground, cones, poles, plateaus).
9. Tests from W14, plus a timing test marked `@pytest.mark.slow` for 6M points (< 30 s).

## Acceptance criteria

- [x] Cone of 20 m on flat ground gives CHM max 20 m +/- 0.5 m at the cone cell.
- [x] 5% slope without trees gives CHM < 0.3 m almost everywhere (99th percentile).
- [x] Ground gaps filled; negative values clipped; a 100 m spike removed and counted.
- [x] Tests pass offline.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_chm.py -q
pytest tests/unit/palmscan/test_scan_chm.py -q -m slow   # perf check, optional
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-022-canopy-height-model-dtm-dsm-chm worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-022
- 2026-11-22 [claude-agent] All 4 acceptance criteria pass: tests/unit/palmscan/test_scan_chm.py 21 passed (cone 20 m +/-0.5, 5% slope p99 < 0.3, gap fill, negative clip, 100 m spike removed+counted, slow 6M-point test 18 s < 30 s). Full suite 903 passed, ruff/format/mypy clean. Commit db24436. Spec notes: plan said griddata over all cells (32+ s); replaced by Delaunay on gap-boundary cells with fixed 0.01 px query offset; added noise classes 7/18 exclusion; outliers counted before hole fill; affine added to dev/scan extras (pyproject.toml added to touches; affine is a rasterio dep but chm.py imports it at module level). ASPRS class codes and EPT Z units/datum marked VERIFY in module docstring; PDAL not used.
- 2026-11-22 [claude-agent] Status in_progress -> review.
