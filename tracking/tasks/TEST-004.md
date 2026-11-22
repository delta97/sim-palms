---
id: TEST-004
title: Add contract conformance tests for palms.geojson
status: todo
phase: 1
area: TEST
kind: test
plan_ref: "plans/detailed/06-testing.md#contract-conformance"
depends_on: [TEST-001, ARCH-002, ARCH-003]
requires: [none]
agent: test-engineer
estimate_h: 3
touches: [tests/helpers/contract.py, tests/unit/contract/test_palms_contract.py, tests/fixtures/contract/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Every `palms.geojson` (fixtures and any local palmscan output) is checked against the schema plus cross-field invariants that JSON Schema can't express. This protects the one shared data contract.

## Context

- Spec: `plans/detailed/06-testing.md#contract-conformance` and the contract part of `#helper-api`.
- Schemas and validators belong to ARCH: `schemas/palms.geojson.schema.json` + `palmcore.contract.validate_palms(doc, mode="read") -> ValidationReport` (ARCH-002), `palmcore.config.load_region()` (ARCH-003), per `plans/detailed/01-architecture.md`. VERIFY (V12) against the merged code; adapt the wrapper, not the tests.
- ARCH already tests every `regions/*.yaml` (`tests/unit/palmcore/test_region_files.py`). Don't repeat that here.
- ARCH's shared fixture `tests/fixtures/palmcore/palms_io/sample_10.geojson` may be copied as the starting valid fixture. Never edit it in place.
- VERIFY (V13): whether `exclusion_radius_m` is exactly `crown_diam_m/2 + margin_m` or clamped. Check `plans/detailed/02-detection-pipeline.md`. If exact, add an equality check (tolerance 0.01 m) when a region is given; otherwise keep `≥ crown_diam_m/2`.

## Steps

1. `tests/helpers/contract.py`:
   - `validate_palms(fc) -> list[str]`: call `palmcore.contract.validate_palms`; turn each error issue of the `ValidationReport` into a readable string (feature index + palm_id + JSON path + message). Warnings are not errors.
   - `check_palms_invariants(fc, *, region=None) -> list[str]`: the invariants listed in the plan (unique `palm_id`, `region` consistent, point inside `bbox`, `exclusion_radius_m ≥ crown_diam_m/2` and > 0, `height_m > 0`, `species_confidence` in [0,1], `height_source == "lidar"` implies `lidar` in `detected_by`).
   - `assert_palms_ok(path_or_fc, *, region=None)`: load path or dict, load region via `palmcore.config.load_region` if a path, raise `AssertionError` listing at most 50 errors plus a count.
   - CLI `python -m tests.helpers.contract <palms.geojson> [--region <yaml>]`: print errors, exit 0 if none, 1 otherwise.
2. Fixtures in `tests/fixtures/contract/`: `valid_minimal.geojson` (3 palms, all fields, using the example from `plans/01-architecture.md` as a pattern), `region_minimal.yaml`, and one invalid file per invariant (`dup_palm_id.geojson`, `outside_bbox.geojson`, `radius_too_small.geojson`, `region_mismatch.geojson`, `lidar_height_without_lidar.geojson`), plus `schema_missing_field.geojson`.
3. `tests/unit/contract/test_palms_contract.py`: valid fixture passes; each invalid fixture fails with an error that names the rule; a parametrized test over `REPO_ROOT.glob("data/**/palms.geojson")` that skips with reason "no local palmscan output" when the list is empty.

## Acceptance criteria

- [ ] Valid fixture passes; every invalid fixture fails with a rule-specific message.
- [ ] Local `data/**/palms.geojson` files are tested when present and skipped cleanly when not.
- [ ] CLI exits 0 on the valid fixture and 1 on an invalid one.

## Verification

```bash
pytest tests/unit/contract -q -ra
python -m tests.helpers.contract tests/fixtures/contract/valid_minimal.geojson --region tests/fixtures/contract/region_minimal.yaml; echo "exit=$?"   # exit=0
python -m tests.helpers.contract tests/fixtures/contract/dup_palm_id.geojson; echo "exit=$?"                                                       # exit=1
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
