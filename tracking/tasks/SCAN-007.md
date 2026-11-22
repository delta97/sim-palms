---
id: SCAN-007
title: "Record live source fixtures and confirm source fields"
status: in_progress
phase: 1
area: SCAN
kind: test
plan_ref: "plans/detailed/02-detection-pipeline.md#w5-recorded-fixtures-and-source-verification"
depends_on: [SCAN-002, SCAN-004, SCAN-006]
requires: [network]
agent: geo-data-engineer
estimate_h: 2
touches: [tests/fixtures/palmscan/recorded/, tests/unit/palmscan/test_scan_recorded_sources.py, palmscan/data/species_aliases.csv, palmscan/data/species_keys.yaml, palmscan/data/non_tree_markers.yaml]
owner: claude-agent
branch: task/scan-007-record-live-source-fixtures-and-confirm
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-007"
updated: 2026-11-22
---

## Goal

Small real responses from each Phase 1 source are saved as fixtures, every VERIFY item about source fields and endpoints is answered in writing, and the species alias table covers the real spellings.

## Context

- Spec: plan_ref section W5, and the VERIFY table in "Open questions and VERIFY items".
- Sources: City of San Diego street trees (ArcGIS layer 20), `stiles/la-trees` on GitHub, OSM Overpass (trees and buildings). Also check whether StreetsLA has a machine-readable endpoint and how Microsoft Global ML Building Footprints are distributed (answer only; no fixture needed).
- Recording bbox: 400 m x 400 m around (-117.2531, 32.7893), or a 400 m clip of TEST-100's T1 if published. For la-trees, a 400 m clip around a known LA palm street.
- Use the adapters themselves with a real `HttpClient` and a cache pointed at a scratch dir, then copy and trim. Keep each fixture under 2 MB. Do not include personal data in any request (generic User-Agent).
- Respect Overpass usage policy: a handful of queries, no loops.

## Steps

1. Write a throwaway recording script outside the repo (scratch dir) that runs each adapter on the recording bbox with a cache rooted in the scratch dir.
2. Copy responses to `tests/fixtures/palmscan/recorded/<source>/` (`sd_street_trees/`, `la_trees/`, `osm_trees/`, `osm_buildings/`), trimmed to the bbox.
3. Write `tests/fixtures/palmscan/recorded/README.md`: per source URL, fetch date, bbox, license note, and the answer to each VERIFY item (field names for species/status/date/id/height and units, pagination, `maxRecordCount`, `lastEditDate`, la-trees layout and URLs, StreetsLA endpoint, Microsoft footprints distribution).
4. List distinct species and status strings in the recordings; add missing palm names, "palm"-named non-palms and status markers to `species_aliases.csv` / `non_tree_markers.yaml` (keep sorted).
5. Add `tests/unit/palmscan/test_scan_recorded_sources.py`: each adapter parses its recording via an offline cache seeded from the fixture files, returns > 0 records, and at least one record per tree source normalizes to a palm.
6. If any VERIFY answer contradicts the plan, note it in this task's Log and in the README so the plan owner can update `plans/detailed/02-detection-pipeline.md`.

## Acceptance criteria

- [ ] Recorded fixtures exist for San Diego trees, la-trees, OSM trees and OSM buildings, each < 2 MB.
- [ ] README answers every SCAN-007 VERIFY item from the plan's table.
- [ ] `test_scan_recorded_sources.py` passes offline.
- [ ] Alias table updated; SCAN-002 tests still pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_recorded_sources.py tests/unit/palmscan/test_scan_species_names.py -q
du -sh tests/fixtures/palmscan/recorded/*      # each under 2 MB
grep -c VERIFY tests/fixtures/palmscan/recorded/README.md   # expect 0 unanswered markers
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Added palmscan/data/species_keys.yaml to touches: any new species key added to the alias table must also be added to the canonical species-key registry (SCAN-002). Cross-area reconciliation.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-007-record-live-source-fixtures-and-confirm worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-007
