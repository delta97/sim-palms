---
id: TEST-102
title: "Visual test protocol tooling: run scaffolder, checklist template, test log"
status: in_progress
phase: 2
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#visual-protocol"
depends_on: [TEST-001, TEST-005]
requires: [none]
agent: test-engineer
estimate_h: 4
touches: [tests/visual/__init__.py, tests/visual/new_run.py, tests/visual/check_run.py, tests/visual/PROTOCOL.md, tests/visual/checklist_template.md, tests/visual/test_log.md, tests/visual/graphics_profile.yaml, tests/visual/.gitignore, tests/unit/visual/test_new_run.py, tests/unit/visual/test_check_run.py]
owner: claude-agent
branch: task/test-102-visual-test-protocol-tooling-run-scaffol
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-102"
updated: 2026-11-22
---

## Goal

One command scaffolds a dated visual run folder, one command turns raw screenshots into named committed images, and one command checks the run and records pass/fail in the test log. The in-sim checklist becomes repeatable.

## Context

- Spec: `plans/detailed/06-testing.md#visual-run-format` and `#visual-protocol`.
- Sites and viewpoints come from `tests/helpers/sites.py` (TEST-005). Refuse to scaffold a run for a site with `status: placeholder` unless `--allow-placeholder`.
- `tests/visual/` also holds ASSET review lineups (`tests/visual/lineup-<species>/`, ASSET-owned). The tools only create and read `tests/visual/T<n>/`; `check_run` and the log ignore other folders.
- Pillow does the JPEG conversion. No sim needed: tests use generated images.
- Storage: finalized JPEG q90 committed in plain git, raw screenshots gitignored, is the plan default. The rule is decided in DEC-008 (ADR-0009, together with asset binaries); if ADR-0009 chooses LFS for screenshots, ASSET-008 adds the `.gitattributes` patterns and nothing here changes except PROTOCOL.md wording.
- Viewpoints: VP1 street (~2 m), VP2 low oblique (~150 m), VP3 approach (~600 m).

## Steps

1. `tests/visual/checklist_template.md`: header (site, date, label, tester), the C1-C8 table with columns VP1, VP2, VP3 (empty cells), a Notes section. Check texts from the plan.
2. `tests/visual/graphics_profile.yaml`: profile `ref-v1` with keys to fill (resolution, preset, render_scaling, upscaler, terrain_lod, object_lod, vsync, frame_cap); values `TBD` until the first real run.
3. `tests/visual/test_log.md`: title, one-line explanation, the empty table from the plan.
4. `tests/visual/.gitignore`: `*/*/raw/`.
5. `tests/visual/new_run.py`:
   - `create` (default subcommand): `--site`, `--date` (default today), `--label`, `--variants` (default `nofix,static`, allowed nofix/static/live), `--sim-version`, `--sdk-version`, `--region-pkg`, `--assets-pkg`, `--tester`, `--graphics-profile` (default `ref-v1`). Creates `tests/visual/<site>/<date>[_<label>]/` with `run.yaml`, `checklist.md`, `raw/<variant>/`. Refuses if the folder exists. Appends a `pending` row to `test_log.md`. Prints the next steps from PROTOCOL.md.
   - `finalize <run_dir>`: for each variant, sort `raw/<variant>/*.{png,jpg,jpeg,bmp}` by mtime; require exactly 3; write `<variant>/VP1_street.jpg`, `VP2_oblique.jpg`, `VP3_approach.jpg` (JPEG q90, downscale to max 2560 px wide, keep aspect). Print the mapping (raw name -> output name). `--order name` sorts by file name instead.
6. `tests/visual/check_run.py <run_dir> [--update-log]`: verify `run.yaml` keys, all expected images, and every checklist cell in {pass, fail, na}. Result pass if no fail and no blank. `--update-log` replaces the matching row's Result in `test_log.md`. Exit 0 pass, 1 fail or incomplete (list problems).
7. `tests/visual/PROTOCOL.md`: the 7 steps from the plan, plus "how to recall viewpoints" pointing to `tests/sites/<site>/` and `docs/findings/TEST-006.md`, and the rule that C8 is `na` before Phase 3.
8. Tests in `tests/unit/visual/`: monkeypatch the visual root to `tmp_path`; `create` makes the expected tree and log row; second `create` refuses; `finalize` with 3 generated PNGs of different mtimes produces the right names and sizes (one 4000 px wide input becomes 2560 px); 2 images -> error; `check_run` passes on a filled checklist, fails on one blank cell and on one `fail` cell; `--update-log` rewrites the right row only.

## Acceptance criteria

- [ ] `create`, `finalize` and `check_run` behave as specified, with tests.
- [ ] Raw screenshots are gitignored; finalized JPEGs are not.
- [ ] `PROTOCOL.md` lets a person run the protocol without reading this task.
- [ ] Placeholder sites are refused by default.

## Verification

```bash
pytest tests/unit/visual -q
python -m tests.visual.new_run --help
python -m tests.visual.check_run --help
git check-ignore -v tests/visual/T1/2027-01-01/raw/nofix/x.png   # prints the .gitignore rule
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Screenshot storage (JPEG q90 in plain git vs Git LFS) is now decided in DEC-008 (ADR-0009); this task implements the plan default and follows ADR-0009 if it differs. Viewpoints are street (~2 m), oblique (~150 m), approach (~600 m). Cross-area reconciliation.
- 2026-11-22 [claude-agent] Claimed. branch=task/test-102-visual-test-protocol-tooling-run-scaffol worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-102
