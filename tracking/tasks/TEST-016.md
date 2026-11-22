---
id: TEST-016
title: Build the independent build-output checker and build-time history
status: todo
phase: 2
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#build-checks"
depends_on: [TEST-015, SPIKE-003, SPIKE-004]
requires: [none]
agent: test-engineer
estimate_h: 4
touches: [tests/helpers/build_checks.py, tests/regression/check_build.py, tests/regression/build_history.csv, tests/unit/regression/test_check_build.py, tests/fixtures/regression/build_sample/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`python -m tests.regression.check_build <build_dir>` independently confirms a `palmgen build` is complete: exit code 0, a BGL per tile, polygon and object counts consistent with the input, and build time recorded so slowdowns show up over time.

## Context

- Spec: `plans/detailed/06-testing.md#build-checks` and the build_checks part of `#helper-api`.
- Package layout: `plans/04-fs2024-integration.md` section 1 (`PackageSources/scene/tile_*.xml`) and `plans/detailed/04-fs2024-integration.md` if it exists (it wins).
- VERIFY items owned here, answered from Phase 0 findings (`docs/findings/SPIKE-003.md`, `docs/findings/SPIKE-004.md`): V7 where `fspackagetool` writes BGLs and whether each tile XML maps to one BGL; V8 the XML element names for exclusion polygons and scenery objects (from the captured templates in `palmgen/templates/`); V9: GEN's plan defines `build_report.json` (`plans/detailed/04-fs2024-integration.md#build-report-fields`): `fspackagetool.exit_code`, `timings.compile_s`/`total_s`, `counts.polygons`/`objects`/`tiles`, `tiles[].{tile_id, polygons, objects, bgl}`. Read exit code and timings from it, but recount polygons, objects and BGL files from disk; a mismatch between GEN's numbers and the recount is itself a failure. VERIFY that GEN-100 ships these keys.
- Independent of GEN's own checks on purpose. Do not import `palmgen`.

## Steps

1. `tests/helpers/build_checks.py`: `count_tile_elements(tile_xml)` using lxml and the element names from the templates (keep them in module constants `POLYGON_TAGS`, `OBJECT_TAGS` with a comment citing the template file); `BuildCheckResult`; `check_build(build_dir, palms=None, *, expect_objects=True)` doing checks 1-4 from the plan. Point-in-polygon for check 3 needs the polygon coordinates from the XML; if the template stores vertices in a form that's hard to parse, limit check 3 to counts and note it.
2. `tests/regression/check_build.py`: CLI `<build_dir> [--palms <geojson>] [--no-objects] [--append-history] [--slowdown-factor 1.5] [--history <csv>]`. Prints a summary table. `--append-history` adds a row to `tests/regression/build_history.csv` (header from the plan) and warns if time per 1,000 polygons > factor × median of the last 5 rows for the region. Exit 0 ok (warnings allowed), 1 a check failed, 2 input error.
3. `tests/regression/build_history.csv`: header row only.
4. Fixture `tests/fixtures/regression/build_sample/`: a minimal tree mirroring the real layout (from the findings): 2 tile XMLs built from the templates with 3 polygons and 4 objects, fake `.bgl` files (a few bytes), a `build_report.json` with the GEN keys above, and a matching 4-palm `palms.geojson`.
5. `tests/unit/regression/test_check_build.py` (copy the fixture to `tmp_path` with `copy_fixture_tree`): passes as is; delete one BGL -> fail naming the tile; remove an object from a tile -> count mismatch; `--no-objects` ignores objects; `fspackagetool.exit_code: 1` in `build_report.json` -> fail; GEN's `tiles[].objects` disagreeing with the recount -> fail; history append and slowdown warning with a seeded CSV.

## Acceptance criteria

- [ ] Checks 1-4 implemented; element names and BGL layout taken from Phase 0 findings, with citations in code comments.
- [ ] Tests pass on the fixture tree.
- [ ] `build_history.csv` gets one row per `--append-history` run.
- [ ] V7, V8, V9 resolved or still marked VERIFY with the reason in the Log.

## Verification

```bash
pytest tests/unit/regression/test_check_build.py -q
python -m tests.regression.check_build tests/fixtures/regression/build_sample --palms tests/fixtures/regression/build_sample/palms.geojson; echo "exit=$?"   # exit=0
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
