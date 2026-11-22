---
id: TEST-003
title: Add geometry assertion helpers for exclusion polygons
status: in_progress
phase: 2
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#geometry-helpers"
depends_on: [TEST-001]
requires: [none]
agent: test-engineer
estimate_h: 3
touches: [tests/helpers/geom.py, tests/unit/helpers/test_geom.py]
owner: claude-agent
branch: task/test-003-add-geometry-assertion-helpers-for-exclu
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-003"
updated: 2026-11-22
---

## Goal

`tests/helpers/geom.py` gives GEN reusable checks for the plan's geometry rules: circles valid and closed, radius within bounds, building clip never invalid or empty, distances in metres.

## Context

- Spec: `plans/detailed/06-testing.md#geometry-helpers` and the geom part of `#helper-api`.
- Geometries are shapely objects in EPSG:4326 (lon, lat). Measure in metres with pyproj (`Geod(ellps="WGS84")` for distances, an `aeqd` projection centred on the geometry for areas).
- Region config default: 12 sides, margin 1.5 m (`plans/01-architecture.md` "Region config").
- Don't depend on `palmgen` or `palmcore` code; the helpers must work on any shapely geometry.

## Steps

1. Implement in `tests/helpers/geom.py`: `distance_m`, `to_local_m`, `assert_valid_polygon`, `assert_ring_closed`, `assert_circle_like`, `assert_radius_within`, `assert_disjoint_from`, `assert_points_close`, with the signatures in the plan.
2. `assert_valid_polygon`: accept Polygon (and MultiPolygon if `allow_multi`); fail on empty, invalid (message includes `shapely.validation.explain_validity`), any unclosed ring, local area below `min_area_m2`, or a MultiPolygon part below `min_area_m2`.
3. `assert_circle_like`: ring has `sides + 1` coordinates and every vertex distance d satisfies `r·cos(π/sides)·(1 − rel_tol) ≤ d ≤ r/cos(π/sides)·(1 + rel_tol)`.
4. `assert_disjoint_from(poly, others, tol_m2)`: for each geometry in `others`, local area of the intersection ≤ `tol_m2`; message names the index and the overlap area.
5. All assertion messages give the measured value and the limit.
6. Tests in `tests/unit/helpers/test_geom.py`, built with a small local helper that makes an n-gon of radius r metres around a lon/lat:
   - 12-gon at r = 3.4 m passes `assert_circle_like` and `assert_valid_polygon`.
   - Same 12-gon scaled 1.1× fails `assert_circle_like` and `assert_radius_within(r_max_m=3.5)`.
   - Bow-tie polygon fails validity. A ring whose last coordinate differs from the first fails `assert_ring_closed` (build the coordinate list by hand; shapely closes rings itself, so test the ring-check function on a raw coordinate sequence too).
   - Polygon overlapping a 10 × 10 m building by about 1 m² fails `assert_disjoint_from`; the same polygon after `difference` passes.
   - `distance_m` between two points 0.001° of latitude apart is about 110.9 m (±0.5).

## Acceptance criteria

- [ ] All helpers exist with the exact signatures in the plan.
- [ ] Self-tests pass and cover one pass and one fail case per helper.
- [ ] Failure messages include measured value and limit.

## Verification

```bash
pytest tests/unit/helpers/test_geom.py -q
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/test-003-add-geometry-assertion-helpers-for-exclu worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-003
