---
id: SCAN-008
title: "Inventory ingest stage and cross-source dedupe"
status: review
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w6-ingest-and-dedupe"
depends_on: [SCAN-002, SCAN-004, SCAN-005]
requires: [none]
agent: geo-data-engineer
estimate_h: 3
touches: [palmscan/sources/registry.py, palmscan/ingest.py, palmscan/detect/dedupe.py, tests/unit/palmscan/test_scan_ingest.py, tests/unit/palmscan/test_scan_dedupe.py]
owner: claude-agent
branch: task/scan-008-inventory-ingest-stage-and-cross-source
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-008"
updated: 2026-11-22
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

- [x] Non-palms are counted, not returned; stumps/vacant become rejects with stage `inventory`.
- [x] Cross-source duplicates within 2 m merge; same-source neighbours never merge.
- [x] Shuffling input order gives identical output.
- [x] Tests pass offline.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_ingest.py tests/unit/palmscan/test_scan_dedupe.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [integrator] integrator note from SCAN-004: source cache_max_age_days is not enforced (palmscan.cache.Cache has no freshness check; palmcore.cache.is_fresh exists) — wire it in at ingest or add it to Cache
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-008-inventory-ingest-stage-and-cross-source worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-008
- 2026-11-22 [claude-agent] Implemented registry.py, ingest.py, detect/dedupe.py + tests (21 pass); full suite 1498 passed 4 skipped, ruff/format/mypy clean. Acceptance all met: non-palms counted/stump+vacant rejected; cross-source merge only, same-source kept; shuffle-invariant output; offline tests. cache_max_age_days enforced in ingest via per-source _FreshnessCache (stale refetched, offline used + warning); tested. height_raw set on PalmRecord (field came from SCAN-009 merge) and tested. Plan W6 refined: dedupe resolves pairs closest-first; osm_adapter test hook; source_order result field. Buildings adapter not registered (not an inventory adapter); hook comment in registry.py.
- 2026-11-22 [claude-agent] Status in_progress -> review.
