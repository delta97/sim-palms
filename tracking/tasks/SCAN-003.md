---
id: SCAN-003
title: "Source adapter base and geojson_file adapter"
status: review
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w3-inventory-and-osm-source-adapters"
depends_on: [SCAN-001]
requires: [none]
agent: geo-data-engineer
estimate_h: 3
touches: [palmscan/sources/base.py, palmscan/sources/geojson_file.py, tests/unit/palmscan/test_scan_geojson_file.py, tests/fixtures/palmscan/geojson_file/]
owner: claude-agent
branch: task/scan-003-source-adapter-base-and-geojson-file-ada
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-003"
updated: 2026-11-22
---

## Goal

A common adapter interface (`InventoryAdapter`, `FetchResult`, `SourceError`, vintage helper) and a working `geojson_file` adapter that reads local or downloaded GeoJSON/CSV tree files (the LA County compilation) clipped to the region bbox.

## Context

- Spec: plan_ref section W3 (base.py and geojson_file.py parts) and the `sources.inventory[]` key table under "Inputs: region config keys".
- Adapters return raw `TreeRecord`s (from `palmscan/model.py`); they do not normalize species.
- The real LA County compilation (github.com/stiles/la-trees) is large (1.6M records). Its exact files and fields are unknown until SCAN-007 records them: build the adapter around config field names, and use synthetic fixtures here.
- Downloads go through `Cache.get_or_fetch("geojson_file", sha1(url), ...)` and `HttpClient.download`. Tests pass a fake HTTP client and an offline cache.

## Steps

1. `palmscan/sources/base.py`: `SourceError`, `FetchResult`, `InventoryAdapter` protocol, `derive_vintage(cfg_vintage, record_dates, layer_edit_ms, fetched_at) -> SourceVintage`, and a `parse_date(value) -> date | None` accepting ISO strings, `MM/DD/YYYY` and epoch milliseconds.
2. `palmscan/sources/geojson_file.py`: `GeoJsonFileAdapter(cfg: InventorySourceCfg)` with `name` and `fetch(bbox, cache, http)`.
   - `url` -> cached download keeping the file name suffix; `path` -> read in place.
   - GeoJSON via `geopandas.read_file(path, bbox=bbox, engine="pyogrio")`; non-point geometries -> representative point + warning count; non-4326 CRS -> reproject + warning.
   - CSV via `csv.DictReader` streaming with `lon_field`/`lat_field`; bad coordinates counted in a warning.
   - Map `species_field`, `common_name_field`, `id_field`, `status_field`, `height_field`, `dbh_field`, `date_field` into `TreeRecord`; id fallback to feature `id` then row index (warning).
   - Vintage via `derive_vintage`.
3. Fixtures in `tests/fixtures/palmscan/geojson_file/`: `trees_sample.geojson` (about 20 points, mixed palms/non-palms, two outside the bbox, one polygon, one missing species), `trees_sample.csv` (same records), `README.md` stating they are synthetic.
4. Tests: bbox clipping, field mapping, id fallback, CSV parity with GeoJSON, URL download through a fake HTTP client into a `tmp_path` cache, vintage from record dates vs config override.

## Acceptance criteria

- [x] GeoJSON and CSV fixtures yield the same records (ids, coordinates, species) inside the bbox.
- [x] Points outside the bbox are excluded; polygon features become points with a warning.
- [x] `derive_vintage` honours the precedence config > record dates > layer edit date > fetched.
- [x] No test touches the network; tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_geojson_file.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-003-source-adapter-base-and-geojson-file-ada worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-003
- 2026-11-22 [claude-agent] Implemented palmscan/sources/base.py and geojson_file.py. Verified: pytest tests/unit/palmscan/test_scan_geojson_file.py 41 passed; full suite 903 passed, 1 skipped; ruff check/format and mypy clean. Plan text fixed: SourceError re-exported from palmcore.errors (not a new class); fetch bbox accepts Bbox or 4-sequence; derive_vintage gained keyword source; CRS and memory behaviour documented (GeoJSON memory on the 627 MB file is VERIFY for SCAN-007). Findings: pyogrio parses ISO date strings to datetime, so reads use datetime_as_string=True; feature-id fallback uses the GDAL FID, which is only reliable when no feature has an id member (warned as unstable).
- 2026-11-22 [claude-agent] Status in_progress -> review.
