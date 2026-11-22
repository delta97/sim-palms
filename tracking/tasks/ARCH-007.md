---
id: ARCH-007
title: "Add the palms.geojson serializer, reader and writer"
status: todo
phase: 1
area: ARCH
kind: build
plan_ref: plans/detailed/01-architecture.md#ws6-palms-read-and-write
depends_on: [ARCH-002, ARCH-004]
requires: [none]
agent: python-architect
estimate_h: 4
touches: [palmcore/palms.py, tests/unit/palmcore/test_palms_io.py, tests/fixtures/palmcore/palms_io/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`palmcore/palms.py` contains:
- a typed `Palm` record;
- one canonical serializer (`dump_palms`), so the same input always gives byte-identical files;
- validating writers (`write_palms_doc`, `write_palms`);
- a reader (`read_palms`) that returns typed palms plus metadata.

palmscan writes through it, and palmgen and TEST read through it, so the file format is defined in exactly one place.

## Context

- Dataclasses, signatures, canonical form (rounding, key order, sorting, `indent=1`), `SOURCE_DATE_EPOCH` and `data_version` rules: plan_ref section WS6.
- The canonical form copies the SCAN plan's rounding and layout (`plans/detailed/02-detection-pipeline.md`, W9 and the field mapping), so SCAN-011's `write_palms(fc, path)` can delegate to `write_palms_doc` (open question Q12).
- GEN's `resolve_data_version` reads the collection metadata. `PalmsMeta.to_dict()` exposes `data_version` (`plans/detailed/04-fs2024-integration.md`).
- Validation comes from `palmcore.contract` (ARCH-002): `write` mode before writing, `read` mode when reading. The field order is the WS5 property table in `plans/detailed/01-architecture.md#ws5-palms-data-contract`.
- Atomic write: `palmcore.cache.atomic_write_text` (ARCH-004). Logging: `palmcore.log.get_logger`.
- `x_*` fields, and unknown fields from a newer minor version, go into `Palm.extra` on read. They are written back after the standard properties, sorted.
- Use hand-written ids matching `^[a-z]{2,6}-[0-9a-f]{16}$` (e.g. `sdc-0000000000000001`). Don't import `palmcore.ids`; this task does not depend on ARCH-006.

## Steps

1. Implement `Palm` (`frozen=True, slots=True`) with `to_feature()` and `from_feature()`. `from_feature` puts the coordinates into `lon`/`lat`, `source_ids` into a tuple, and every non-standard property into `extra`.
2. Implement `PalmsMeta` (with `to_dict()`) and `PalmCollection` (with `by_id()`).
3. Implement `dump_palms(doc)`:
   - deep-copy the doc;
   - round the values;
   - normalise `-0.0`;
   - sort `source_ids` and the features;
   - always set feature `id`;
   - order the keys;
   - emit `json.dumps(..., indent=1, ensure_ascii=False, allow_nan=False) + "\n"`.

   NaN or inf → `ContractError`.
4. Implement `write_palms_doc(path, doc)`: canonicalise, `validate_palms(mode="write")`, raise `ContractError` before touching the disk, then `atomic_write_text` (parent dirs created).
5. Implement `write_palms(path, palms, *, region, generator_name, generator_version, config_sha256, generated_at, data_version)`: build the doc (`generated_at` from the argument, then `SOURCE_DATE_EPOCH`, then now; `data_version` from the argument, then the `YYYY-MM` of `generated_at`), call `write_palms_doc`, and return `PalmsMeta`.
6. Implement `read_palms`: load the JSON; validate in `read` mode (just `check_version` when `validate=False`); log warnings; raise on errors; return palms sorted by `palm_id`.
7. In the test module, write a helper that builds 10 varied `Palm`s (every `detected_by` value at least once, one `ground_elev_m=None`, one `x_note` extra). Use it to create `tests/fixtures/palmcore/palms_io/sample_10.geojson` with `generated_at=2026-01-01T00:00:00Z`, generator `palmscan 0.1.0`, `config_sha256=None`. Commit the file.
8. Write `tests/unit/palmcore/test_palms_io.py`:
   - write → read gives equal `Palm` lists (after rounding);
   - the same palms in a different input order give byte-identical files;
   - a fresh `write_palms` of the helper palms equals the committed `sample_10.geojson` byte for byte (golden check);
   - rounding: lon `-117.253112345` → `-117.2531123`; `height_m` `22.46` → `22.5`; `exclusion_radius_m` `3.456` → `3.46`; `species_confidence` `0.954` → `0.95`; `-0.0` → `0.0`;
   - `source_ids` come out sorted;
   - NaN in `height_m` raises `ContractError` and writes no file;
   - an invalid palm (radius < crown/2) raises `ContractError` and leaves an existing file unchanged;
   - empty input writes a valid file, and reading it logs one warning;
   - reading `tests/fixtures/palmcore/palms/newer_minor_1_1.geojson` keeps `canopy_class` in `extra` and logs one version warning (`caplog`);
   - `SOURCE_DATE_EPOCH=1767225600` gives `generated_at` `2026-01-01T00:00:00Z` and `data_version` `2026-01`;
   - `dump_palms` of an already-canonical doc returns the same text (idempotent).
9. Run the Verification commands.

## Acceptance criteria

- [ ] A test proves that identical input gives byte-identical output.
- [ ] `write_palms_doc` and `write_palms` never write an invalid file.
- [ ] `sample_10.geojson` is committed, valid and reproducible.
- [ ] ruff, mypy (strict for palmcore) and pytest are green.

## Verification

```bash
pytest tests/unit/palmcore/test_palms_io.py -q
python -c "from pathlib import Path; from palmcore.palms import read_palms; c=read_palms(Path('tests/fixtures/palmcore/palms_io/sample_10.geojson')); print(len(c.palms), c.meta.schema_version, c.meta.data_version)"   # 10 1.0 2026-01
ruff check palmcore tests && mypy
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
