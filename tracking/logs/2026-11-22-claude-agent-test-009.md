# Session log: 2026-11-22, claude-agent, test-009

- **Started / ended:** 2026-11-22 (time not recorded)
- **Agent / model / person:** claude-agent (Claude Haiku 5.5)
- **Branch / worktree:** task/test-009-define-the-ground-truth-format-and-write, `C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-009`
- **Tasks:** TEST-009 (in_progress -> review)

## Goal

Define the ground-truth format for palm accuracy tests, write the labeling guide, and build the
`tests.accuracy.gt` tooling (`init-site`, `validate`, `fill-heights`, `next-id`) plus the library
loaders that TEST-010 will import. No labels were made; the fixtures are synthetic.

## What changed

- `tests/accuracy/ground_truth.schema.json`: JSON Schema (2020-12) for `ground_truth.geojson`. Properties and enums follow `plans/detailed/06-testing.md#ground-truth-format`; `gt_id` pattern is `^T[0-9]+-gt-[0-9]{4}$`.
- `tests/accuracy/gt.py`: format helpers (`height_class`, `site_dir`), checks (`validate_site`), loaders (`load_ground_truth`, `load_labeled_area`, `load_meta`), commands (`init_site`, `fill_heights`, `next_id`), and the CLI. The `fill-heights` sampler imports rasterio inside the function.
- `tests/accuracy/LABELING.md`: the labeling procedure, written so it stands without the task file. Covers NAIP WMS setup, QGIS Value Map widgets, crown-centre and cluster rules, strip sweep, species basis, saving at 7 decimals, `validate`, and a table of common errors.
- `tests/accuracy/__init__.py`: empty package marker.
- `tests/unit/accuracy/test_gt.py`: 38 tests (schema, height edges, each invalid fixture, cross-file rules, loaders, `init-site` including refusal of placeholder sites, `next-id`, `fill-heights` against a synthetic CHM, rasterio-missing message, CLI exit codes, `--help`).
- `tests/fixtures/accuracy/gt/{valid,dup_id,outside_area,bad_enum}/T9/`: synthetic site T9 in a Null Island box (0..0.01 deg). Each file is marked SYNTHETIC.
- `tracking/tasks/TEST-009.md`: three acceptance boxes ticked with evidence; Log entries.
- `tracking/logs/2026-11-22-claude-agent-test-009.md`: this file.

## Verification

- `python -m pytest tests/unit/accuracy/test_gt.py -q -ra`: 38 passed, none skipped (rasterio 1.5.2 installed in `.venv`).
- `python -m pytest -q -m "not network and not sim"`: 920 passed, 1 skipped (pre-existing palmscan CHM check).
- `python -m ruff check .`: all checks passed. `python -m ruff format --check .`: clean. `python -m mypy`: no issues in 48 files.
- `python -m tests.accuracy.gt --help`: lists the four commands.
- `python scripts/tasks.py validate`: 213 tasks, 0 errors, 0 warnings.

## Decisions and findings

- **Height classes are defined once**, in `gt.height_class`: S < 8 m, M 8 to < 15, T 15 to < 25, X >= 25. TEST-010 must import this rather than redefine it.
- **Species check is the pattern only.** `palmscan/data/species_keys.yaml` (SCAN-002) is not on main. Once it lands, `validate` should also check species against it. Recorded in LABELING.md section 6.
- **Species and basis must agree**: `unknown` species needs basis `unknown`, and the reverse. This is a rule I added; the plan does not state it.
- **Coordinates must have at most 7 decimals** (LABELING.md step 9). Enforced by `validate`, because the plan asks for precision 7.
- **Labels must be blind to predictions.** LABELING.md asks labellers not to open `palms.geojson` while labelling.
- **Height from the CHM is optional and after the classes.** The plan (step 4) says the CHM may help with the height class. I kept it optional but told labellers to judge classes from imagery first, because height-class agreement is the independent check. No plan text was changed.
- **VERIFY V14 (NAIP):** the WMS GetCapabilities request returned HTTP 200 on 2026-11-22 for `https://imagery.nationalmap.gov/arcgis/services/USGSNAIPImagery/ImageServer/WMSServer`, which lists layer `USGSNAIPImagery:NaturalColor`. Whether it draws in QGIS, and how the capture year is read, is still VERIFY on first use.
- **Not checked by the tooling:** QGIS version and the exact menu and option names (Value Map, the GeoJSON coordinate precision option). Both are VERIFY in LABELING.md.
- **Site ids** are restricted to `T<n>` (the regex in `gt.site_dir`). Consistent with the five registry sites.

## Open issues

- Species registry check waits on SCAN-002 (`palmscan/data/species_keys.yaml`).
- The CHM-based `fill-heights` is exercised only on a synthetic CHM. A real CHM from SCAN-101 is not available yet.
- TEST-100 has not defined T1..T5, so `init-site` refuses every site today. This is by design (placeholder check).

## Handoff: next steps

1. The integrator reviews branch `task/test-009-define-the-ground-truth-format-and-write` against the TEST-009 acceptance criteria. Run `python -m pytest tests/unit/accuracy/test_gt.py -q -ra` first.
2. After merge, TEST-010 imports `tests.accuracy.gt` (`load_ground_truth`, `load_labeled_area`, `load_meta`, `height_class`). It must not redefine the height classes or the matching fields.
3. When SCAN-002 merges, add a species-registry check to `validate_site` and the `species` row in LABELING.md section 6.
4. TEST-101 (human labeling at T1 and T2) follows LABELING.md. Run `python -m tests.accuracy.gt init-site T1` only after TEST-100 defines the site.
