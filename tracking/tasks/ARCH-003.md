---
id: ARCH-003
title: "Define the region YAML config schema and loader"
status: todo
phase: 1
area: ARCH
kind: build
plan_ref: plans/detailed/01-architecture.md#ws7-region-config
depends_on: [ARCH-001, ARCH-005]
requires: [none]
agent: python-architect
estimate_h: 5
touches: [schemas/region.schema.json, palmcore/config.py, tests/unit/palmcore/test_config.py, tests/fixtures/palmcore/regions/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`schemas/region.schema.json` and `palmcore/config.py`. Together they load `regions/<name>.yaml` into a frozen `RegionConfig`, with defaults applied, absolute paths, the raw mapping kept, and every problem reported in one clear error. Adding a city then means adding a YAML file, not changing code.

## Context

- Key tables (top level, inventory item, mask item), defaults, ranges, dataclasses, signatures, path rule, parsing rules and fixtures: plan_ref section WS7.
- The key set merges the source plan with requests from SCAN (`plans/detailed/02-detection-pipeline.md`, Inputs: inventory keys, `buildings_path`, `overpass_url`, the `palmscan:` block, mask shape) and GEN (`plans/detailed/04-fs2024-integration.md`, Region config keys palmgen reads: extra `exclusion.*` keys, `placement.scale_clamp`, `masks.airports.*`, mask `kind`/`geometry`). Where they disagreed, WS7 records the choice (open questions Q13–Q15).
- `palmscan` and `palmgen` are free-form mappings. Validate only that they are objects; SCAN and GEN check their own keys.
- Versioning: `config_version: 1`; rules in `plans/detailed/01-architecture.md#ws10-data-contract-versioning-policy`. The CHANGELOG entry is written by ARCH-002; do not touch `schemas/CHANGELOG.md`.
- Uses `palmcore.geo.Bbox` and `local_crs_for` (ARCH-005), and `load_schema("region")`, `make_validator` and `ConfigError` (ARCH-001).
- `load_region` takes `regions_dir`/`base_dir` arguments rather than `palmcore.paths.Paths`, so this task doesn't depend on ARCH-004.
- The real example regions are ARCH-008. Use fixtures only here.

## Steps

1. Write `schemas/region.schema.json` (Draft 2020-12, `$id: "urn:palmfix:schema:region:1"`). Use `additionalProperties: false` everywhere except `options`, `palmscan`, `palmgen` and mask `geometry`. Express these with `if`/`then` or `oneOf`: `arcgis_rest` requires `url`; `geojson_file` needs exactly one of `url`/`path`; a mask needs exactly one of `bbox`/`geometry`/`path`; `lidar`/`buildings` accept a string, `null` or `{type, options}`. Put defaults in `default` keywords.
2. Implement `palmcore/config.py` with the WS7 dataclasses and functions: `SUPPORTED_CONFIG_VERSIONS`, `InventorySource`, `TypedSource`, `Sources`, `ExclusionConfig`, `PlacementConfig`, `MaskArea`, `AirportMasks`, `RegionConfig` (`crs()`, `to_dict()`), `load_region`, `load_region_dict`, `list_regions`, `check_regions`.
3. Implement `_UniqueKeyLoader(yaml.SafeLoader)`, which raises `ConfigError` on a duplicate mapping key and reports the line number.
4. Loading pipeline:
   1. Read the bytes and compute sha256.
   2. Parse the YAML. The top level must be a mapping.
   3. Check `config_version` with a clear message before the schema runs.
   4. Run the schema with `iter_errors`: all errors, sorted, one line each, prefixed with the file path and dotted key path.
   5. Run the semantic checks: stem match; `Bbox`; unique inventory and mask names; priors ≥ 0 with sum > 0, then normalise to 1; csv `lon_field`/`lat_field` once the format is known from `format` or the file extension; `radius_min_m <= radius_max_m`; `local_crs` parses with `pyproj.CRS.from_user_input`.
   6. Fill defaults, including the `id_prefix` default (initials of the `-`-parts of `region`).
   7. Resolve relative `path`/`buildings_path` values against `base_dir`.
   8. Build the dataclasses and keep `raw`.
   9. Log a warning for any mask bbox outside the region bbox.
5. Create the fixtures in `tests/fixtures/palmcore/regions/` listed in WS7. That means `minimal.yaml` (`region: minimal`), `full.yaml` (`region: full`, every key), `invalid/*.yaml` plus `invalid/expected.json` (file → expected substring), and `dup_prefix/` with two valid files sharing one `id_prefix`.
6. Write `tests/unit/palmcore/test_config.py`:
   - `minimal.yaml` loads, every default equals the dataclass defaults, and `id_prefix` defaults to the initials;
   - `full.yaml` round-trips: `load_region_dict(cfg.to_dict(), base_dir=...)` equals `cfg`, ignoring `source_path`, `sha256` and `raw`;
   - each invalid case raises `ConfigError` containing the expected substring; `unknown_key` names the key and its dotted path;
   - two independent errors in one file are both reported in one exception;
   - priors `{a_b: 2, c_d: 2}` normalise to 0.5/0.5;
   - relative `path` values come back absolute under `base_dir`;
   - `check_regions(dup_prefix_dir)` returns one error naming both files;
   - `list_regions` skips `_*.yaml` and non-yaml files;
   - schema `default` keywords equal the Python defaults (parse the schema JSON and compare);
   - a slug containing `../` raises `ConfigError` before any file access.
7. Run the Verification commands.

## Acceptance criteria

- [ ] Every error names the file and the dotted key path.
- [ ] Duplicate YAML keys are rejected.
- [ ] Defaults are defined once in Python, and a test checks the schema `default` values against them.
- [ ] `RegionConfig` and its parts are frozen; paths are absolute; `raw` holds the parsed YAML; `sha256` is the hash of the raw bytes.
- [ ] ruff, mypy (strict for palmcore) and pytest are green.

## Verification

```bash
pytest tests/unit/palmcore/test_config.py -q
python -c "from palmcore.config import load_region; c=load_region('tests/fixtures/palmcore/regions/minimal.yaml'); print(c.region, c.id_prefix, c.exclusion.margin_m, c.crs())"
ruff check palmcore tests && mypy
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
