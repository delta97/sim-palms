---
id: ARCH-002
title: "Define the palms.geojson JSON Schema and a shared validator"
status: in_progress
phase: 1
area: ARCH
kind: build
plan_ref: plans/detailed/01-architecture.md#ws5-palms-data-contract
depends_on: [ARCH-001]
requires: [none]
agent: python-architect
estimate_h: 6
touches: [schemas/palms.geojson.schema.json, schemas/buildings.geojson.schema.json, schemas/CHANGELOG.md, palmcore/contract.py, tests/unit/palmcore/test_contract.py, tests/fixtures/palmcore/palms/, tests/fixtures/palmcore/buildings/]
owner: claude-agent
branch: task/arch-002-define-the-palms-geojson-json-schema-and
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ARCH-002"
updated: 2026-11-22
---

## Goal

`schemas/palms.geojson.schema.json` (schema 1.0) and `palmcore/contract.py`. The module validates a palms document against the schema and the semantic rules S1–S9, with version-aware read and write modes. This is the contract between palmscan and palmgen, palmlive and the TEST metrics.

## Context

- File keys, the property table (types, ranges, enums), S1–S9, read/write/relaxed modes and the fixture list: plan_ref section WS5.
- Versioning: `plans/detailed/01-architecture.md#ws10-data-contract-versioning-policy`. This task also writes `schemas/CHANGELOG.md`, with the policy text and the initial entries for **both** schemas (palms `1.0`, region `config_version 1`), so ARCH-003 never touches that file.
- The enum values come from the SCAN field mapping in `plans/detailed/02-detection-pipeline.md` (palms.geojson field mapping). `data_version` (`YYYY-MM`) is requested by GEN (`plans/detailed/04-fs2024-integration.md`, package versioning).
- Uses `palmcore.schemas.load_schema("palms")`, `make_validator()` and `palmcore.errors.ContractError` from ARCH-001.
- The `bbox` argument is a plain 4-tuple, so this module doesn't depend on `palmcore.geo`.
- `palm_id` pattern `^[a-z]{2,6}-[0-9a-f]{16}$` follows ARCH-006. Fixture ids only need to match the pattern (e.g. `sdc-0000000000000001`).
- SCAN and TEST wrap this as `validate_palms(fc) -> list[str]`. Provide `ValidationReport.error_strings(limit)` for that.
- `ground_elev_m` is `number or null` and required: palmscan writes `null` in Phase 1 (no DTM yet). Its unit and datum are documented in the schema `description`: metres, orthometric height of the ground at the palm point, `VERIFY:` against the 3DEP vertical datum (usually NAVD88; SCAN-021/SCAN-101 confirm). Informational only; GEN snaps to sim ground.
- `data_version` (`YYYY-MM`, required, file level) is the collection key GEN's `resolve_data_version` reads for `+data2026-11`.
- `species` stays a pattern, not an enum. The canonical list of species keys is `palmscan/data/species_keys.yaml` (SCAN-002); SCAN normalization and ASSET manifest validation check against that registry, and SCAN-002 tests that every registry key matches this schema pattern.
- Secondary contract: `buildings.geojson` (palmscan writes it next to `palms.geojson` in `build/scan/<region>/`; palmgen reads it for clipping). Minimal schema per WS5 "buildings.geojson": `type` FeatureCollection, `schema_version` `1.0`, `region` slug, features with Polygon/MultiPolygon WGS84 geometry and required properties `building_id` (string, unique) and `source` (string); extra properties allowed.

## Steps

1. Write `schemas/palms.geojson.schema.json` (Draft 2020-12, `$id: "urn:palmfix:schema:palms:1"`). Top level per the WS5 file table, including required `data_version`. Feature under `$defs/feature`; its `properties` use `additionalProperties: false` plus `patternProperties: {"^x_[a-z0-9_]+$": {}}`. Add a `$comment` pointing to `schemas/CHANGELOG.md`.
2. Write `schemas/CHANGELOG.md`: the WS10 policy (short form), then `## palms.geojson 1.0 (2026-11-21)` and `## region config_version 1 (2026-11-21)`, each with a one-line description.
3. Implement `palmcore/contract.py` with the names and signatures from WS5: `PALMS_SCHEMA_VERSION`, `SUPPORTED`, `ValidationIssue`, `ValidationReport` (including `error_strings` and `to_dict`), `parse_version`, `check_version`, `validate_palms`, `validate_palms_file`, plus `validate_buildings(doc) -> ValidationReport` against `schemas/buildings.geojson.schema.json` (write that schema too; `$id: "urn:palmfix:schema:buildings:1"`; unique `building_id` is a semantic check).
4. Follow the WS5 validation order (steps 1–5). Compile the strict and relaxed feature validators once (module-level cache). Validate the envelope with `features: []`.
5. Paths look like `features[12].properties.height_m`. Messages are jsonschema's `error.message`. Sort issues per feature by path, so the output is stable.
6. Create the fixtures listed in WS5 in `tests/fixtures/palmcore/palms/`, including `invalid/expected.json`, and `tests/fixtures/palmcore/buildings/` (`valid_small.geojson`, `invalid_duplicate_id.geojson`, `invalid_point_geometry.geojson`).
7. Write `tests/unit/palmcore/test_contract.py`:
   - every `valid_*.geojson` passes in read mode; `valid_minimal` and `valid_small` also pass in write mode;
   - `newer_minor_1_1.geojson` passes in read mode with exactly one version warning (unknown property and new enum value tolerated) and has errors in write mode;
   - a table-driven test over `invalid/expected.json`: each file has at least one error whose path equals `path` and whose message contains `contains`;
   - `major_2.geojson` raises `ContractError` in both modes;
   - `parse_version` accepts `"1.0"` and `"1.12"` and rejects `"1"`, `"v1.0"`, `"1.0.0"`;
   - the `bbox` argument triggers S5 and the `region` argument triggers S2;
   - `max_errors=3` on a file with 10 bad features gives 3 errors and `truncated=True`;
   - `error_strings(limit=2)` returns 2 strings in the documented format;
   - a compatibility test globbing `valid_v1_*.geojson` passes when the glob is empty and asserts each match is valid;
   - `@pytest.mark.slow`: 10,000 synthetic valid features validate in under 15 s.
8. Run the Verification commands.

## Acceptance criteria

- [ ] The schema passes `Draft202012Validator.check_schema`.
- [ ] Each of S1–S9 has at least one test.
- [ ] `validate_palms` reports schema errors instead of raising, for supported versions. It raises only for a malformed or unsupported major version.
- [ ] Issue strings follow `error features[i] <palm_id>: <path>: <message>`.
- [ ] `schemas/CHANGELOG.md` holds the policy and both initial entries.
- [ ] `ground_elev_m: null` validates; the schema `description` states metres, orthometric, `VERIFY:` 3DEP datum.
- [ ] `validate_buildings` accepts the valid buildings fixture and rejects both invalid ones.
- [ ] ruff, mypy (strict for palmcore) and pytest are green.

## Verification

```bash
pytest tests/unit/palmcore/test_contract.py -q
pytest tests/unit/palmcore/test_contract.py -q -m slow
python -c "from pathlib import Path; from palmcore.contract import validate_palms_file as v; r=v(Path('tests/fixtures/palmcore/palms/valid_small.geojson')); print(r.ok, r.feature_count)"   # True 10
ruff check palmcore tests && mypy
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Added buildings.geojson secondary contract (schemas/buildings.geojson.schema.json, validate_buildings), documented ground_elev_m datum (metres, orthometric, VERIFY vs 3DEP) and nullability, confirmed data_version is GEN's data-version key, noted the species-key registry (SCAN-002 palmscan/data/species_keys.yaml). Cross-area reconciliation.
- 2026-11-22 [claude-agent] Claimed. branch=task/arch-002-define-the-palms-geojson-json-schema-and worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ARCH-002
