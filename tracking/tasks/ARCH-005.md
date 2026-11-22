---
id: ARCH-005
title: "Add palmcore geo helpers (Bbox, distances, UTM, transforms)"
status: review
phase: 1
area: ARCH
kind: build
plan_ref: plans/detailed/01-architecture.md#ws3-geo-helpers
depends_on: [ARCH-001]
requires: [none]
agent: geo-data-engineer
estimate_h: 3
touches: [palmcore/geo.py, tests/unit/palmcore/test_geo.py]
owner: claude-agent
branch: task/arch-005-add-palmcore-geo-helpers-bbox-distances
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ARCH-005"
updated: 2026-11-22
---

## Goal

`palmcore/geo.py`: a validated `Bbox` type, great-circle distance, metres per degree, automatic UTM CRS selection and cached pyproj transforms. SCAN and GEN share these, so axis order and CRS handling are defined in one place.

## Context

- Signatures, formulas and test values: plan_ref section WS3.
- Allowed dependencies: the standard library and `pyproj` only. No shapely, numpy or geopandas in `palmcore`.
- Axis order is always (lon, lat) / (x, y). Use `always_xy=True`.
- Out of scope: circles, unions, building clipping, tiling (GEN's `palmgen/geometry.py`, `palmgen/tiling.py`).
- ARCH-003 imports `Bbox` and `local_crs_for`. SCAN plans a `palmscan/geo.py` that wraps these when present. Keep the names exact.

## Steps

1. Implement `WGS84`, `EARTH_RADIUS_M`, `Bbox` (`__post_init__` validation, `from_list`, `to_list`, `as_tuple`, `contains`, `intersects`, `center`, `buffer_m`, `width_m`, `height_m`), `haversine_m`, `meters_per_degree`, `utm_epsg`, `local_crs_for`, `transformer` (`functools.cache`), `to_local`, `to_wgs84`.
2. `Bbox.__post_init__` raises `ValueError` naming the bad value, for: non-finite values, out-of-range values, `lon_min >= lon_max`, `lat_min >= lat_max`. The docstring says the antimeridian is not supported.
3. `Bbox.buffer_m` converts metres to degrees at the centre latitude and clamps to ±180/±90.
4. `local_crs_for(bbox, override)` validates an override with `pyproj.CRS.from_user_input` and raises `ValueError` if it doesn't parse.
5. Write `tests/unit/palmcore/test_geo.py` with every WS3 test value:
   - UTM zones: San Diego → 32611, Sydney → 32756, lon 180 → zone 60;
   - haversine: 0.001° lat ≈ 111.2 m ± 0.2 on the sphere (110.9 m is `meters_per_degree(32.79)[1]/1000`, also tested); symmetric; zero for identical points;
   - `meters_per_degree(0)` ≈ (111320, 110574) within 5 m;
   - `Bbox`: rejects the four invalid shapes; `contains` on an edge is True; `intersects` with a touching bbox is True; `buffer_m(100)` grows each side by about 100 m ± 1 m;
   - `to_local` → `to_wgs84` round trip error < 1e-7°;
   - `transformer` returns the same object for the same arguments.
6. Run the Verification commands.

## Acceptance criteria

- [x] All names and signatures match WS3.
- [x] Imports are limited to the standard library and `pyproj`.
- [x] Every WS3 test value is covered.
- [x] ruff, mypy (strict for palmcore) and pytest are green.

## Verification

```bash
pytest tests/unit/palmcore/test_geo.py -q
python -c "from palmcore.geo import Bbox, local_crs_for; print(local_crs_for(Bbox(-117.28, 32.70, -117.15, 32.82)))"   # EPSG:32611
ruff check palmcore tests && mypy
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/arch-005-add-palmcore-geo-helpers-bbox-distances worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ARCH-005
- 2026-11-22 [claude-agent] Implemented palmcore/geo.py + tests (4fbbb07). pytest: 44 passed; ruff check/format clean; mypy: Success, no issues in 6 source files; local_crs_for(San Diego bbox) = EPSG:32611.
- 2026-11-22 [claude-agent] Spec fix: WS3 said haversine of 0.001 deg lat = 110.9 m, but on the fixed sphere (R=6371008.8) it is 111.195 m; 110.9 m is meters_per_degree(32.79)[1]/1000. Both asserted in tests; WS3 and task text corrected.
- 2026-11-22 [claude-agent] Status in_progress -> review.
