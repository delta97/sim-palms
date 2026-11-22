# Session log: 2026-11-22, claude-agent, test-102

- **Started / ended:** 2026-11-22 (local time, not recorded)
- **Agent / model / person:** claude-agent (Claude Haiku 5.5), test-engineer role
- **Branch / worktree:** task/test-102-visual-test-protocol-tooling-run-scaffol, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-102
- **Tasks:** TEST-102 (in_progress -> review)

## Goal

Build the visual test protocol tooling from plans/detailed/06-testing.md#visual-protocol: a run
scaffolder, a finalizer for screenshots, a checker that records pass or fail in the test log, and
the checklist, graphics profile, log and protocol documents that go with them.

## What changed

- `tests/visual/__init__.py`: package docstring.
- `tests/visual/new_run.py`: `create` (default) makes `tests/visual/<site>/<date>[_<label>]/` with `run.yaml`, `checklist.md`, `raw/<variant>/` and appends a pending log row. Refuses placeholder sites unless `--allow-placeholder`. `finalize` writes `VP1_street.jpg`, `VP2_oblique.jpg`, `VP3_approach.jpg` per variant (JPEG q90, max 2560 px wide), ordered by mtime or `--order name`.
- `tests/visual/check_run.py`: checks `run.yaml` keys, images per variant, and every checklist cell (pass, fail or na). Exit 0 pass, 1 fail or incomplete, 2 bad input. `--update-log` sets the Result cell.
- `tests/visual/PROTOCOL.md`: the 7-step runbook for a person on the sim PC, with VERIFY marks for camera and flight method.
- `tests/visual/checklist_template.md`: header fields, C1 to C8 table with VP1/VP2/VP3 columns, Notes.
- `tests/visual/graphics_profile.yaml`: profile `ref-v1`, every value TBD.
- `tests/visual/test_log.md`: title, explanation, empty table in the plan's column order.
- `tests/visual/.gitignore`: `*/*/raw/`.
- `tests/unit/visual/test_new_run.py`, `tests/unit/visual/test_check_run.py`: 53 tests using generated images and a temp layout.
- `tracking/tasks/TEST-102.md`: fixed two stale lines in Context and Step 7 (see Decisions), acceptance boxes ticked, log entries.

## Verification

- `pytest tests/unit/visual -q`: 53 passed.
- `pytest -q` (full, with the gen and scan extras installed): 935 passed, 1 skipped (sim-output contract test, expected).
- `ruff check .`, `ruff format --check .`, `mypy`: clean.
- `python -m tests.visual.new_run --help` and `python -m tests.visual.check_run --help`: exit 0.
- `git check-ignore -v tests/visual/T1/2027-01-01/raw/nofix/x.png`: matched by `tests/visual/.gitignore:1:*/*/raw/`. A finalized `.../nofix/VP1_street.jpg` is not ignored.
- Real CLI on the committed registry: `new_run --site T1` exits 2 with the placeholder message and creates nothing; `--site T9` exits 2 listing known sites.
- `python scripts/tasks.py validate`: 213 tasks, 0 errors, 0 warnings.

## Decisions and findings

- Run folders follow the plan's form `tests/visual/<site>/<date>[_<label>]/`. The task's Context said `T<n>/`; that was stale, and the task text is fixed.
- Viewpoint recall points to the single registry `tests/sites/sites.yaml`, not `tests/sites/<site>/` (no such folders exist). The task's Step 7 is fixed.
- `tester` and `sdk_version` default to `VERIFY`, and `check_run` will not pass while they are `VERIFY`. This is a deliberate guard against a run with no named tester.
- `run.yaml` records `flight` (null until TEST-100) and `site_status`, in addition to the plan's keys.
- `check_run` leaves Result as `pending` for an incomplete run with no fail cell, and writes `fail` for any fail cell.
- Pillow is needed only by `finalize`. It is in the `dev` extra, but `pyproject.toml` is not in the task's `touches`, so the sim-PC install path is open (see Open issues).
- The plan cites DEC-008 and ADR-0009 for screenshot storage. Neither is on this branch; PROTOCOL.md marks the Git LFS question VERIFY.

## Open issues

1. Pillow is not a runtime dependency. The user needs `pip install -e ".[dev]"` or `pip install pillow` on the sim PC before `finalize`. Fix in a follow-up: a `visual` extra, or add to the `dev` extra's use notes, with `pyproject.toml` added to `touches`.
2. VERIFY (TEST-006 and TEST-100): flight reload method, camera placement method per viewpoint, screenshot save location and format, whether community packages need a sim restart. Marked in PROTOCOL.md.
3. The protocol has not been run by a person on the sim PC. Acceptance box "PROTOCOL.md lets a person run the protocol" is ticked on a self-check of its content, and a reviewer should confirm it.
4. `graphics_profile.yaml` values are TBD until the first real run records them.

## Handoff: next steps

1. Reviewer (code-reviewer or the integrator): read `tests/visual/PROTOCOL.md` cold and confirm it is followable without the task file; run `python -m tests.visual.new_run --help` and `pytest tests/unit/visual -q`.
2. Integrator: decide whether Pillow goes into a `visual` extra (needs `pyproject.toml` in `touches`); see Open issues 1.
3. TEST-100 (user, sim PC) defines the sites. Then run `python -m tests.visual.new_run --site T1 --label phase2 --sim-version <v> --region-pkg <ver>` as in PROTOCOL.md, and fill the TBD values in `graphics_profile.yaml` in the same commit as the first real run.
4. TEST-006 (user, sim PC) answers the VERIFY items in PROTOCOL.md before the user runs step 3.
