# Session log: 2026-11-22, claude-agent, scan-003 source adapter base and geojson_file

- **Started / ended:** 2026-11-22
- **Agent / model / person:** claude-agent
- **Branch / worktree:** task/scan-003-source-adapter-base-and-geojson-file-ada, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-003
- **Tasks:** SCAN-003 (in_progress -> review)

## Goal

Add the common inventory adapter interface and a working `geojson_file` adapter (GeoJSON via pyogrio, CSV streamed), tested offline on synthetic fixtures.

## What changed

- `palmscan/sources/base.py`: `FetchResult`, `InventoryAdapter`, `SourceError` (re-export of palmcore's), `parse_date`, `derive_vintage`, `as_bbox`.
- `palmscan/sources/geojson_file.py`: `GeoJsonFileAdapter`; URL download through the cache, bbox clip, non-point to point, CRS reprojection, CSV streaming.
- `tests/fixtures/palmscan/geojson_file/`: synthetic GeoJSON and CSV (20 records) plus README.
- `tests/unit/palmscan/test_scan_geojson_file.py`: 41 tests.
- `plans/detailed/02-detection-pipeline.md` W3: aligned with the implementation (commit 785ee64).

## Verification

- `pytest tests/unit/palmscan/test_scan_geojson_file.py -q`: 41 passed. Full suite: 903 passed, 1 skipped. ruff check, ruff format --check, mypy: clean.

## Decisions and findings

- `SourceError` is reused from `palmcore.errors`; a second class would not share its exit code.
- pyogrio turns ISO date strings into datetimes; reads use `datetime_as_string=True` to keep raw text.
- GeoJSON feature-id fallback is the GDAL FID; reliable only when no feature has its own id member. Warned as unstable.
- Memory on the 627 MB LA County file is unmeasured (file not local). CSV is fully streamed; GeoJSON relies on the OGR spatial filter. VERIFY in SCAN-007; fallback is converting to GeoPackage/FlatGeobuf.

## Open issues

- Peak memory on the real LA County GeoJSON (SCAN-007).

## Handoff: next steps

1. Reviewer checks SCAN-003 against the acceptance criteria; SCAN-007 measures real-file memory.
