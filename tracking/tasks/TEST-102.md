---
id: TEST-102
title: "Visual test protocol tooling: run scaffolder, checklist template, test log"
status: review
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
- `tests/visual/` also holds ASSET review lineups (`tests/visual/lineup-<species>/`, ASSET-owned). The tools only create and read `tests/visual/<site>/<date>[_<label>]/` (plan form; the older `T<n>/` wording here was stale), and `check_run` and the log ignore other folders.
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
7. `tests/visual/PROTOCOL.md`: the 7 steps from the plan, plus "how to recall viewpoints" pointing to the site's entry in `tests/sites/sites.yaml` (the registry is one file, not per-site folders) and `docs/findings/TEST-006.md`, and the rule that C8 is `na` before Phase 3.
8. Tests in `tests/unit/visual/`: monkeypatch the visual root to `tmp_path`; `create` makes the expected tree and log row; second `create` refuses; `finalize` with 3 generated PNGs of different mtimes produces the right names and sizes (one 4000 px wide input becomes 2560 px); 2 images -> error; `check_run` passes on a filled checklist, fails on one blank cell and on one `fail` cell; `--update-log` rewrites the right row only.

## Acceptance criteria

- [x] `create`, `finalize` and `check_run` behave as specified, with tests.
- [x] Raw screenshots are gitignored; finalized JPEGs are not.
- [x] `PROTOCOL.md` lets a person run the protocol without reading this task.
- [x] Placeholder sites are refused by default.

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
- 2026-11-22 [claude-agent] Built tests/visual: new_run.py (create, finalize), check_run.py, PROTOCOL.md, checklist_template.md, graphics_profile.yaml (ref-v1, TBD values), test_log.md, .gitignore (*/*/raw/). Commit pending.
- 2026-11-22 [claude-agent] Tests: pytest tests/unit/visual -q -> 53 passed (create tree and log row, second create refused, placeholder refused by default and by CLI exit 2, finalize mtime/name order and 4000 px downscale to 2560, 2-image and mismatched-variant refusals, check_run pass/blank/fail/missing image/VERIFY, --update-log on the right row only). Full suite: 935 passed, 1 skipped (sim-output contract test). ruff check, ruff format --check, mypy clean.
- 2026-11-22 [claude-agent] Acceptance: create/finalize/check_run per spec with tests; raw/ ignored (git check-ignore: */*/raw/ rule matches tests/visual/T1/2027-01-01/raw/nofix/x.png; a finalized .jpg is not ignored); PROTOCOL.md self-checked for all 7 steps and prerequisites (a person with the sim has not yet run it); placeholder sites refused (real CLI on committed registry exits 2, writes nothing).
- 2026-11-22 [claude-agent] Spec discrepancies resolved: (1) Context said tools use tests/visual/T<n>/; plan and Steps say tests/visual/<site>/<date>[_<label>]/, followed the plan and fixed the Context text. (2) PROTOCOL viewpoint recall pointed to tests/sites/<site>/; the registry is the single tests/sites/sites.yaml, so PROTOCOL points there and the task text is fixed. (3) Plan cites DEC-008 / ADR-0009 for screenshot storage; neither file is on this branch, so PROTOCOL marks the LFS question VERIFY.
- 2026-11-22 [claude-agent] Design choices for the integrator: tester and sdk_version default to VERIFY and check_run refuses to pass while they are VERIFY; run.yaml also records flight (null until TEST-100) and site_status; a placeholder run needs --allow-placeholder and is for rehearsal only. Pillow is needed only by finalize; it is in the dev extra, but pyproject.toml is not in touches, so runtime install for the sim PC is left to a follow-up (add a visual extra or core dep).
- 2026-11-22 [claude-agent] VERIFY open items for TEST-006/TEST-100: flight reload and camera placement method, screenshot save location and format, whether community packages need a restart (all marked VERIFY in PROTOCOL.md).
- 2026-11-22 [claude-agent] Status in_progress -> review.
