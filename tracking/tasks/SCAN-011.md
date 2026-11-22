---
id: SCAN-011
title: "palms.geojson writer, palm IDs and schema validation"
status: in_progress
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w9-output-writer-and-palm-ids"
depends_on: [SCAN-001, ARCH-002, ARCH-006, ARCH-007]
requires: [none]
agent: python-architect
estimate_h: 2
touches: [palmscan/output.py, tests/unit/palmscan/test_scan_output.py, tests/fixtures/palmscan/output/]
owner: claude-agent
branch: task/scan-011-palms-geojson-writer-palm-ids-and-schema
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-011"
updated: 2026-11-22
---

## Goal

`palmscan/output.py` turns `PalmRecord`s into a schema-valid, byte-deterministic `palms.geojson` with stable `palm_id`s, and refuses to write invalid output.

## Context

- Spec: plan_ref section W9 and "palms.geojson field mapping" (rounding, ordering, enums).
- ARCH-002 provides `schemas/palms.geojson.schema.json` and a validator in `palmcore`. Read them first. Where the plan's enum values, nullable `ground_elev_m`, `data_vintage` keys or `palm_id` pattern disagree with the schema, the schema wins: adapt the writer and note the difference in this task's Log (plan Q3, Q4, Q12).
- Ids: `palmcore.ids.palm_id(prefix, stable_key)` (ARCH-006; `<prefix>-<16 hex>`, the schema pattern). No local sha1 fallback; use `palmcore.ids.assert_unique` for the collision check.
- Writing: `palmcore.palms.write_palms_doc(path, fc)` (ARCH-007) owns the canonical form (rounding, key order, sorting, `indent=1`, trailing newline, atomic write, validate-before-write). This module must not reimplement any of it.
- Output path: canonical `build/scan/<region>/palms.geojson` (the caller passes it).

## Steps

1. `assign_palm_ids(palms, prefix)`: stable key rules from W9; `palmcore.ids.palm_id(prefix, key)`; a duplicate id (same key from two records) is an error naming both records.
2. `to_feature_collection(palms, region)`: contract field order, rounding, sorted `source_ids`, `null` for unknown `ground_elev_m`, features sorted by `palm_id`.
3. `validate_palms(fc) -> list[str]` wrapping the ARCH-002 validator.
4. `write_palms(fc, path)`: delegates to `palmcore.palms.write_palms_doc`. On `ContractError` the caller writes `palms.invalid.geojson` (provide `write_invalid(fc, dir)` helper, plain `json.dumps`, no validation).
5. Fixture `tests/fixtures/palmscan/output/expected_palms.geojson` from a fixed list of 5 records (inventory, genus-only, prior, building conflict, LiDAR-only style).
6. Tests: golden byte comparison; ids stable under input shuffling; a duplicate stable key is reported; every fixture feature validates; an invalid record (negative height) yields errors.

## Acceptance criteria

- [ ] Golden test passes byte-for-byte.
- [ ] Shuffled input gives the identical file.
- [ ] Output validates with the ARCH-002 validator; invalid input is rejected with readable messages.
- [ ] Any schema/plan mismatch is recorded in the Log.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_output.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Depends on ARCH-006 and ARCH-007 (ARCH request). Removed duplicate implementation scope: palm ids come from palmcore.ids.palm_id (16 hex, schema pattern), writing delegates to palmcore.palms.write_palms_doc (canonical rounding/layout, atomic write); this task keeps only PalmRecord -> FeatureCollection mapping, the validate wrapper and the invalid-output helper. Cross-area reconciliation.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-011-palms-geojson-writer-palm-ids-and-schema worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-011
