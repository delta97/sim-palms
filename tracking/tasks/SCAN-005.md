---
id: SCAN-005
title: "Overpass client and OSM tree adapter"
status: review
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w3-inventory-and-osm-source-adapters"
depends_on: [SCAN-003]
requires: [none]
agent: geo-data-engineer
estimate_h: 2
touches: [palmscan/sources/overpass.py, palmscan/sources/osm_overpass.py, tests/unit/palmscan/test_scan_osm_overpass.py, tests/fixtures/palmscan/osm_overpass/]
owner: claude-agent
branch: task/scan-005-overpass-client-and-osm-tree-adapter
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-005"
updated: 2026-11-22
---

## Goal

A reusable `OverpassClient` (cached, tiled, retrying) and `OsmTreesAdapter`, which returns OSM `natural=tree` nodes that carry species/genus/taxon tags as `TreeRecord`s.

## Context

- Spec: plan_ref section W3, `overpass.py` and `osm_overpass.py` parts.
- Default endpoint `https://overpass-api.de/api/interpreter`, overridable by `sources.overpass_url`. Overpass bbox order is (south, west, north, east).
- SCAN-006 (buildings) reuses `OverpassClient`; keep its API exactly `OverpassClient(http, cache, url)` + `query(ql) -> dict`.
- OSM data is ODbL; attribution goes into QA and fixture READMEs.

## Steps

1. `palmscan/sources/overpass.py`: `DEFAULT_OVERPASS_URL`, `OverpassClient.query(ql)` (POST `data=ql`, cache namespace `overpass`, key sha1(ql)), `bbox_tiles(bbox, max_deg=0.05)`, `query_bbox(template, bbox)` that formats `(S,W,N,E)` per tile and merges elements by `(type, id)`; `remark` containing `runtime error` -> `SourceError`.
2. `palmscan/sources/osm_overpass.py`: `OsmTreesAdapter(overpass, name="osm")` using the query in W3; `species_raw` = first of `species`, `genus`, `taxon`, `species:en`; `common_name_raw` = `species:en`; `source_id` = `node/<id>`; untagged nodes dropped and counted; vintage `YYYY-MM` of fetch, basis `fetched`.
3. Fixtures: `trees_response.json` (palm, non-palm, untagged, genus-only nodes), `runtime_error.json`, `README.md`.
4. Tests: parsing, tag precedence, untagged count, runtime error, tile splitting (a 0.12 deg bbox -> 9 tiles) and merge without duplicates, cache reuse.

## Acceptance criteria

- [x] Fixture yields records only for tagged nodes, with `source_id` like `node/123`.
- [x] A bbox of 0.12 x 0.12 deg is split into 9 queries; duplicate elements across tiles appear once.
- [x] Runtime-error remark raises `SourceError`.
- [x] Tests pass offline.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_osm_overpass.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [integrator] integrator note from ARCH-008: Overpass returns HTTP 406 without a User-Agent header; send a generic client UA. Larger queries can 502 (at capacity): retry with backoff
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-005-overpass-client-and-osm-tree-adapter worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-005
- 2026-11-22 [claude-agent] All 4 acceptance criteria met: pytest tests/unit/palmscan/test_scan_osm_overpass.py passes offline (fixture -> 5 tagged records node/<id>, 3 untagged dropped; 0.12 deg bbox -> 9 queries, duplicates merged; runtime-error remark -> SourceError, not cached). Full suite 937 passed; ruff and mypy clean. Plan W3 note added.
- 2026-11-22 [claude-agent] Status in_progress -> review.
