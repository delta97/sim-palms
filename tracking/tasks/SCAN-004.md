---
id: SCAN-004
title: "ArcGIS REST inventory adapter with paging and cache"
status: in_progress
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w3-inventory-and-osm-source-adapters"
depends_on: [SCAN-003]
requires: [none]
agent: geo-data-engineer
estimate_h: 3
touches: [palmscan/sources/arcgis_rest.py, tests/unit/palmscan/test_scan_arcgis_rest.py, tests/fixtures/palmscan/arcgis_rest/]
owner: claude-agent
branch: task/scan-004-arcgis-rest-inventory-adapter-with-pagin
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-004"
updated: 2026-11-22
---

## Goal

`ArcGisRestAdapter` pulls every tree point in the bbox from an ArcGIS MapServer/FeatureServer layer (City of San Diego street trees, layer 20), with paging, a no-pagination fallback, error handling and per-page caching.

## Context

- Spec: plan_ref section W3, `arcgis_rest.py` steps 1-7.
- The San Diego URL in the region example is `https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20` with `species_field: SPECIES_NAME`. Field names, pagination support and `maxRecordCount` are VERIFY items for SCAN-007; do not hard-code them.
- ArcGIS returns HTTP 200 with an `error` object on failure; detect it.
- Use `HttpClient.get_json` and `Cache.get_or_fetch` (namespace `arcgis_rest`, key = sha1 of URL + sorted params). Tests use a fake HTTP client keyed on params.

## Steps

1. Implement `ArcGisRestAdapter(cfg)` in `palmscan/sources/arcgis_rest.py`.
2. Layer info `GET <url>?f=json`: read `maxRecordCount` (default 1000), `objectIdField` (default `OBJECTID`), `advancedQueryCapabilities.supportsPagination`, `editingInfo.lastEditDate`, `fields`; raise `SourceError` if `species_field` is missing.
3. Paged query with the exact params listed in W3; page size `min(maxRecordCount, 2000)`; continue while `exceededTransferLimit` is true or a page is full.
4. Fallback when pagination is unsupported: `returnIdsOnly=true`, then `objectIds` chunks.
5. `error` key -> `SourceError(code, message)`; null geometry skipped and counted; stop with `SourceError` above 200,000 records.
6. Map attributes to `TreeRecord` via config field names; `source_id` = object id; vintage via `derive_vintage` with `lastEditDate`.
7. Synthetic fixtures in `tests/fixtures/palmscan/arcgis_rest/`: `layer_info.json`, `layer_info_nopaging.json`, `query_page_0.json` (full page, `exceededTransferLimit: true`), `query_page_1.json` (partial), `ids_only.json`, `query_by_ids.json`, `error.json`, `README.md` (synthetic, shape follows the Esri JSON format).
8. Tests: two-page pull, no-paging fallback, error response, missing species field, null geometry, cache reuse (second fetch makes zero HTTP calls), offline cache miss raises `CacheMiss`.

## Acceptance criteria

- [ ] Two-page fixture returns all records in object-id order with correct lon/lat.
- [ ] No-pagination fallback returns the same records.
- [ ] An `error` body raises `SourceError` containing the code and message.
- [ ] Second run with a warm cache performs no HTTP calls.
- [ ] Tests pass with no network access.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_arcgis_rest.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [integrator] integrator note from ARCH-008: StreetsLA has only a GeoServer WFS (EPSG:2229), no ArcGIS REST; LA Westside config uses the stiles/la-trees GeoJSON instead (627 MB county file, common names only, id field stability VERIFY)
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-004-arcgis-rest-inventory-adapter-with-pagin worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-004
