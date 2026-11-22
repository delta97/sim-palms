---
id: SCAN-006
title: "Building footprints adapter (OSM, Microsoft file)"
status: in_progress
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w4-building-footprints"
depends_on: [SCAN-005]
requires: [none]
agent: geo-data-engineer
estimate_h: 3
touches: [palmscan/sources/buildings.py, tests/unit/palmscan/test_scan_buildings.py, tests/fixtures/palmscan/buildings/]
owner: claude-agent
branch: task/scan-006-building-footprints-adapter-osm-microsof
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-006"
updated: 2026-11-22
---

## Goal

`fetch_buildings(cfg, cache, http)` returns valid building polygons for the bbox from OSM (via Overpass) or a local Microsoft footprints file, used for the building-conflict flag (Phase 1) and the LiDAR building rule (Phase 4).

## Context

- Spec: plan_ref section W4.
- Output GeoDataFrame columns: `building_id`, `source`, `geometry` (EPSG:4326).
- OSM multipolygon buildings need ring assembly; use `out geom` so member geometries come inline.
- Microsoft footprints download is manual for now; the adapter only reads `sources.buildings_path` (GeoJSON, GeoJSON-lines or GPKG). How they are distributed is a VERIFY item for SCAN-007.

## Steps

1. Implement `fetch_buildings` in `palmscan/sources/buildings.py` dispatching on `cfg.buildings` (`osm`, `microsoft_footprints`, `None`).
2. OSM: query from W4 via `OverpassClient.query_bbox`; closed ways -> Polygon; multipolygon relations -> `shapely.ops.polygonize` outer rings minus inner rings; unclosed ways skipped and counted; ids `way/<id>`, `relation/<id>`.
3. Microsoft: `pyogrio` read with bbox; GeoJSON-lines handled; ids `msbf:<row>`.
4. `None`: empty GeoDataFrame with the right columns and a warning string returned alongside (return `(gdf, warnings)`).
5. `shapely.make_valid`, drop empties, explode collections to polygons.
6. Fixtures: `overpass_buildings.json` (simple way, unclosed way, multipolygon with courtyard, self-intersecting way), `ms_footprints_sample.geojsonl`, `README.md`.
7. Tests: polygon counts, courtyard hole present (area check), invalid polygon repaired, unclosed way counted, Microsoft read clipped to bbox, empty case.

## Acceptance criteria

- [ ] Multipolygon fixture produces one polygon with an interior ring of the expected area (+/- 1%).
- [ ] All output geometries are valid and non-empty.
- [ ] `buildings: null` returns an empty frame plus the plan's warning text.
- [ ] Tests pass offline.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_buildings.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [integrator] integrator note from SCAN-005: reuse palmscan.sources overpass.query_bbox(template, bbox) (placeholders {south},{west},{north},{east} or {bbox})
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-006-building-footprints-adapter-osm-microsof worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-006
