---
id: SCAN-008
title: "Inventory ingest stage and cross-source dedupe"
status: todo
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w6-ingest-and-dedupe"
depends_on: [SCAN-002, SCAN-004, SCAN-005]
requires: [none]
agent: geo-data-engineer
estimate_h: 3
touches: [palmscan/sources/registry.py, palmscan/ingest.py, palmscan/detect/dedupe.py, tests/unit/palmscan/test_scan_ingest.py, tests/unit/palmscan/test_scan_dedupe.py]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`ingest_inventory()` turns all configured inventory sources plus OSM trees into normalized `PalmRecord`s with species, confidence, vintage and rejects, and `dedupe_cross_source()` merges the same palm seen by two sources within 2 m.

## Context

- Spec: plan_ref section W6.
- Config order of `sources.inventory[]` is priority order. An inventory source failure aborts (exit 4 later); an OSM failure is a warning.
- Same-source points within 2 m are both kept (tight palm clusters are real).
- Uses `normalize_species`, `non_tree_reason`, `palm_filter` (SCAN-002), adapters (SCAN-003/004/005), `geo.to_local` (SCAN-001).

## Steps

1. `palmscan/sources/registry.py`: `ADAPTERS` dict and `build_inventory_adapters(cfg)`; unknown type -> `ConfigError`.
2. `palmscan/ingest.py`: `IngestResult` and `ingest_inventory(cfg, cache, http, adapters=None)` following the per-record steps in W6 (stable key `source:source_id`, confidence 0.95 / 0.8 / None for `palm_unknown`, `species_source` and `detected_by` = `inventory` or `osm`, vintage per record or per source, `height_raw` kept on the record via `extra` or a field, counts per source, `unmatched_palm_names` counter).
3. OSM trees after inventories when `sources.osm_trees`; failures appended to `warnings`.
4. `palmscan/detect/dedupe.py`: `dedupe_cross_source(palms, radius_m=2.0, source_priority=None)` per the W6 algorithm with `cKDTree`; deterministic tie-breaks; rejects `stage="dedupe"`, `reason="duplicate_of:<stable_key>"`.
5. Tests with in-memory fake adapters: counts per category, genus-only confidence, unmatched palm names, OSM failure tolerated, inventory failure raised; dedupe: cross-source pair at 1.5 m merged with species upgrade, same-source pair at 1.5 m kept, pair at 2.1 m kept, three sources on one palm collapse to one record with three `source_ids`, output order stable under input shuffling.

## Acceptance criteria

- [ ] Non-palms are counted, not returned; stumps/vacant become rejects with stage `inventory`.
- [ ] Cross-source duplicates within 2 m merge; same-source neighbours never merge.
- [ ] Shuffling input order gives identical output.
- [ ] Tests pass offline.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_ingest.py tests/unit/palmscan/test_scan_dedupe.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
