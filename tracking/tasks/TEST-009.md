---
id: TEST-009
title: Define the ground-truth format and write the labeling guide and tooling
status: in_progress
phase: 4
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#ground-truth-format"
depends_on: [TEST-005]
requires: [none]
agent: test-engineer
estimate_h: 3
touches: [tests/accuracy/__init__.py, tests/accuracy/ground_truth.schema.json, tests/accuracy/gt.py, tests/accuracy/LABELING.md, tests/unit/accuracy/test_gt.py, tests/fixtures/accuracy/gt/]
owner: claude-agent
branch: task/test-009-define-the-ground-truth-format-and-write
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-009"
updated: 2026-11-22
---

## Goal

A schema, a QGIS labeling guide and a small CLI (`init-site`, `validate`, `fill-heights`) so a person can hand-label palms at a site and get a file the metrics script can trust.

## Context

- Spec: `plans/detailed/06-testing.md#ground-truth-format` and `#labeling-procedure`.
- Site bboxes come from `tests/helpers/sites.py` (TEST-005).
- `fill-heights` samples a CHM GeoTIFF with rasterio. The CHM is a palmscan Phase 4 output (SCAN-101); its path is passed on the command line. rasterio is a palmscan dependency, so import it inside the function and give a clear message if missing.
- VERIFY (V14): a working NAIP WMS/WMTS URL for QGIS. Try the USGS/USDA national map services; if no URL can be confirmed from this container, write the step as "add NAIP via QGIS Browser > WMS/WMTS; VERIFY the URL on first use" and leave the VERIFY in LABELING.md.

## Steps

1. `tests/accuracy/__init__.py` (empty).
2. `tests/accuracy/ground_truth.schema.json`: FeatureCollection of Point features with the properties and enums in the plan table. `gt_id` pattern `^T[0-9]+-gt-[0-9]{4}$`. `additionalProperties: false` on properties except `note`.
3. `tests/accuracy/gt.py` with subcommands (run as `python -m tests.accuracy.gt`):
   - `init-site <site>`: create `tests/accuracy/<site>/` with an empty `ground_truth.geojson` (FeatureCollection, `features: []`), `labeled_area.geojson` (polygon from the site bbox), and `meta.yaml` skeleton (`site`, `imagery: {source: TBD, date: TBD, resolution_m: TBD}`, `labelers: []`, `labeled_on: null`, `notes: ""`). Refuse if the folder exists.
   - `validate <site>`: schema check; unique `gt_id`; every point inside `labeled_area.geojson`; `meta.yaml` has no `TBD`; print counts by `context`, `confidence`, `height_class`, `species`. Exit 0/1.
   - `fill-heights <site> --chm <tif> [--radius-m 1.5]`: for each point, CHM max within the radius (window read in the CHM's CRS after reprojecting the point); write `height_ref_m` rounded to 0.1; leave null where no data. Print how many were filled.
   - `next-id <site>`: print the next free `gt_id` (helps labeling).
   - Library functions: `load_ground_truth(site) -> dict`, `load_labeled_area(site) -> shapely Polygon`, `load_meta(site) -> dict`. The metrics script (TEST-010) imports these.
4. `tests/accuracy/LABELING.md`: the step list in the plan, expanded: QGIS version used, adding the basemap, loading the layers, setting Value Map widgets per enum (list each field and its values), crown-centre rule, the strip sweep, low-confidence rule, species basis rule (no copying predictions), saving as GeoJSON in EPSG:4326 with coordinate precision 7, and running `validate`. Add a "time budget" note: about 2 minutes per palm including species lookup.
5. Fixtures `tests/fixtures/accuracy/gt/`: a small valid site (10 points, area polygon, meta) and invalid variants (duplicate id, point outside area, bad enum). A tiny synthetic CHM GeoTIFF (20 × 20 px, 0.5 m) created in the test with rasterio if available, else skip that test.
6. `tests/unit/accuracy/test_gt.py`: init-site into a tmp root; validate passes and fails as expected; fill-heights writes the expected max from the synthetic CHM; next-id.

## Acceptance criteria

- [ ] Schema, CLI and LABELING.md exist; LABELING.md is usable without this task file.
- [ ] `validate` catches the three invalid fixtures.
- [ ] `fill-heights` test passes (or skips cleanly without rasterio).

## Verification

```bash
pytest tests/unit/accuracy/test_gt.py -q -ra
python -m tests.accuracy.gt --help
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/test-009-define-the-ground-truth-format-and-write worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-009
