---
id: ASSET-005
title: "Asset manifest schema, species spec format, loader and generator (palmcore.assets)"
status: review
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#manifest-contract"
depends_on: [ARCH-001]
requires: [none]
agent: python-architect
estimate_h: 5
touches: [schemas/asset-manifest.schema.json, palmcore/assets/__init__.py, palmcore/assets/manifest.py, palmcore/assets/__main__.py, assets/library.yaml, tests/unit/palmcore/test_asset_manifest.py, tests/fixtures/palmcore/assets/manifest/]
owner: claude-agent
branch: task/asset-005-asset-manifest-schema-species-spec-forma
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ASSET-005"
updated: 2026-11-22
---

## Goal

`python -m palmcore.assets build-manifest` and `validate` exist and are tested. `assets/manifest.json` can then be generated from `assets/library.yaml` + `assets/species/*.yaml`, and GEN gets a typed loader (`load_manifest`) for the contract in the plan_ref.

## Context

- The contract (fields, rules, example) is in `#manifest-contract`. The GUID rule is in `#guid-policy`. Naming is in `#naming-conventions`.
- This task only uses the species yaml and computed values. Measured fields (`native_height_m`, `crown_diam_m`, `lods[].triangles`) take the yaml target values or `null` until ASSET-006 fills them from glTF, and `lods[].min_size` stays `null` until ASSET-007. Make the generator pluggable: a function that takes a model directory and returns measured stats, defaulting to 'not measured'.
- ARCH-001 provides `pyproject.toml` and the `palmcore` package. If `jsonschema` or `PyYAML` aren't declared dependencies, log a request to the ARCH owner and don't edit `pyproject.toml` yourself.
- Species keys: the ARCH-002 palms schema uses a pattern (`^[a-z]+(_[a-z]+)+$`), not an enum. The canonical list of keys is `palmscan/data/species_keys.yaml` (SCAN-002). `validate_manifest` checks every species key and `species_fallback` key/target against that registry, read by path relative to the repo root (palmcore must not import palmscan); if the file doesn't exist yet, fall back to the pattern check and print a warning.
- `palmcore/assets/` and `schemas/asset-manifest.schema.json` are ASSET's (no ARCH task touches them). GEN loads the manifest only through `load_manifest` from this module (GEN-011).
- Synthetic fixtures only. No real exports exist yet.

## Steps

1. Write `schemas/asset-manifest.schema.json` (JSON Schema draft 2020-12) for every field in the contract. `model_guid` uses pattern `^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`. `variant` uses pattern `^(short|medium|tall)(_b)?$`. `lods` has exactly 4 items.
2. In `palmcore/assets/manifest.py`: frozen dataclasses `Manifest`, `Species`, `Variant`, `Lod`; `NAMESPACE`; `model_name(species, variant)`; `model_guid(model_name)`; `simobject_title(species, variant)`; `load_species_specs(assets_dir)`; `load_library(assets_dir)`; `build_manifest(assets_dir, measure=None) -> dict`; `dump_manifest(dict) -> str` (sorted keys, indent 2, trailing newline); `load_manifest(path) -> Manifest`; `validate_manifest(path) -> list[str]` (schema, unique GUIDs, GUID == uuid5(name), fallback targets exist, species keys in the registry, package version matches the package definition if present).
3. Leave out species with `status: draft`. Sort variants by `native_height_m`, then `variant`.
4. In `palmcore/assets/__main__.py`: argparse CLI with `build-manifest [--assets-dir] [--out] [--check] [--include-draft]` and `validate [--manifest]`. `--include-draft` keeps draft species, for preview manifests in `build/` only. Exit codes: 0 ok, 1 failures, 2 usage or IO error.
5. Create `assets/library.yaml` with the values in the plan_ref (`package_version: 0.1.0`, scale limits 0.85/1.15, fallbacks).
6. Fixtures in `tests/fixtures/palmcore/assets/manifest/`: a mini assets dir with `library.yaml` and two species yamls (one draft), and an expected `manifest.json`.
7. Tests in `tests/unit/palmcore/test_asset_manifest.py`: GUID determinism and a hard-coded expected value for one name; title formatting incl. `_b`; draft exclusion; byte-identical output across two runs; `--check` returns 1 on a stale file; `validate` catches duplicate GUID, wrong GUID, bad fallback target, schema violation, species key missing from a fixture registry.

## Acceptance criteria

- [x] `pytest tests/unit/palmcore/test_asset_manifest.py -q` passes.
- [x] `build-manifest` on the fixture dir reproduces the expected fixture `manifest.json` byte for byte.
- [x] `load_manifest` returns typed objects. GEN can call `manifest.species['washingtonia_robusta'].variants[0].model_guid`.
- [x] No timestamps or absolute paths appear in the output.

## Verification

```bash
pytest tests/unit/palmcore/test_asset_manifest.py -q
python -m palmcore.assets build-manifest --assets-dir tests/fixtures/palmcore/assets/manifest --out /tmp/m.json
diff /tmp/m.json tests/fixtures/palmcore/assets/manifest/manifest.json && echo SAME
python -m palmcore.assets validate --manifest tests/fixtures/palmcore/assets/manifest/manifest.json; echo $?   # expect 0
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Species keys are validated against the canonical registry palmscan/data/species_keys.yaml (SCAN-002), read by path (palmcore must not import palmscan); the ARCH-002 schema uses a pattern, not an enum. Loader path palmcore.assets.manifest.load_manifest confirmed as the one GEN uses; palmcore/assets/ is ASSET-owned (no ARCH task touches it). Cross-area reconciliation.
- 2026-11-22 [claude-agent] Claimed. branch=task/asset-005-asset-manifest-schema-species-spec-forma worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ASSET-005
- 2026-11-22 [claude-agent] Implemented palmcore.assets (manifest.py, __main__.py, __init__.py), schemas/asset-manifest.schema.json, assets/library.yaml, fixtures. Commit ff5c63b plus follow-up. Verification: test_asset_manifest.py 35 passed; full suite 149 passed; ruff check and format clean; mypy strict clean. build-manifest on fixture dir diffs SAME against expected manifest.json; validate exits 0 (warning: palmscan/data/species_keys.yaml absent, pattern check only). All 4 acceptance boxes ticked.
- 2026-11-22 [claude-agent] Schema not registered in palmcore/schemas.py SCHEMA_FILES (not in touches): loaded as load_schema('asset-manifest.schema.json') via schema_dir(). Integrator may add an 'asset-manifest' key later. Registry file format is unknown (SCAN-002 not here): _load_registry accepts a list, a mapping, or {species|keys|species_keys: list|mapping}; confirm when SCAN-002 lands. VERIFY (ASSET-004): package definition version location; validate reads a Version element/attribute from PackageDefinitions/palmfix-assets.xml if present.
- 2026-11-22 [claude-agent] Resolved scale/fallback overlap: manifest (library.yaml) owns scale_limits and species_fallback defaults; region placement.scale_clamp and species_priors only override. Order: species variants, species_fallback[species], region species_priors if non-empty, species_fallback._default. Documented in plans/detailed/03-palm-assets.md ('Scale limits and species fallback', open question 21). Plan 04 / GEN-011 needs the matching edit (not my section). Note for integrator: no .gitattributes and autocrlf=true here; --check and the byte-for-byte test normalise CRLF, but consider eol=lf for assets/manifest.json.
- 2026-11-22 [claude-agent] Status in_progress -> review.
