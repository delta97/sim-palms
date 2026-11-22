---
id: SCAN-011
title: "palms.geojson writer, palm IDs and schema validation"
status: todo
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w9-output-writer-and-palm-ids"
depends_on: [SCAN-001, ARCH-002]
requires: [none]
agent: python-architect
estimate_h: 2
touches: [palmscan/output.py, tests/unit/palmscan/test_scan_output.py, tests/fixtures/palmscan/output/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`palmscan/output.py` turns `PalmRecord`s into a schema-valid, byte-deterministic `palms.geojson` with stable `palm_id`s, and refuses to write invalid output.

## Context

- Spec: plan_ref section W9 and "palms.geojson field mapping" (rounding, ordering, enums).
- ARCH-002 provides `schemas/palms.geojson.schema.json` and a validator in `palmcore`. Read them first. Where the plan's enum values, nullable `ground_elev_m`, `data_vintage` keys or `palm_id` pattern disagree with the schema, the schema wins: adapt the writer and note the difference in this task's Log (plan Q3, Q4, Q12).
- Use palmcore's deterministic id helper if it exists; otherwise the plan's sha1 fallback with collision lengthening.

## Steps

1. `assign_palm_ids(palms, prefix)`: stable key rules from W9; palmcore helper or `f"{prefix}-{sha1(key)[:10]}"`; detect collisions and lengthen to 12 then 16 hex for the colliding pair.
2. `to_feature_collection(palms, region)`: contract field order, rounding, sorted `source_ids`, `null` for unknown `ground_elev_m`, features sorted by `palm_id`.
3. `validate_palms(fc) -> list[str]` wrapping the ARCH-002 validator.
4. `write_palms(fc, path)`: `json.dumps(indent=1, ensure_ascii=False)` + trailing newline; atomic write. On validation errors the caller writes `palms.invalid.geojson` (provide `write_invalid(fc, dir)` helper).
5. Fixture `tests/fixtures/palmscan/output/expected_palms.geojson` from a fixed list of 5 records (inventory, genus-only, prior, building conflict, LiDAR-only style).
6. Tests: golden byte comparison; ids stable under input shuffling; forced collision (monkeypatch the hash) resolves; every fixture feature validates; an invalid record (negative height) yields errors.

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
