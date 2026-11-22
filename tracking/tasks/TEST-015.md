---
id: TEST-015
title: Write the post-update regression routine, log and entry scaffolder
status: review
phase: 2
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#regression"
depends_on: [TEST-001]
requires: [none]
agent: test-engineer
estimate_h: 2
touches: [tests/regression/__init__.py, tests/regression/ROUTINE.md, tests/regression/LOG.md, tests/regression/new_entry.py, tests/unit/regression/test_new_entry.py]
owner: claude-agent
branch: task/test-015-write-the-post-update-regression-routine
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-015"
updated: 2026-11-22
---

## Goal

A written routine to run after every sim or SDK update, a log with one row per update, and a command that adds the row and a notes file. Exclusions have broken in past updates; this is how breakage gets caught the same day.

## Context

- Spec: `plans/detailed/06-testing.md#regression` and `#regression-log-format`.
- The routine refers to tools from other TEST tasks (visual protocol TEST-102, build checker TEST-016, image diff TEST-008, perf TEST-103). Reference them by command; they don't need to exist for this task.

## Steps

1. `tests/regression/__init__.py` (empty).
2. `tests/regression/LOG.md`: title, one paragraph (when to run, link to ROUTINE.md), the empty table from the plan.
3. `tests/regression/ROUTINE.md`: steps 0-5 from the plan, each with the exact command, what pass means, and roughly how long it takes. Include the "if anything fails" step (deactivate region packages, check DevSupport, file a bug, log in RISK).
4. `tests/regression/new_entry.py`: `--trigger {SU,hotfix,beta,SDK}`, `--sim-version`, `--sdk-version`, `--date` (default today), `--root` (for tests). Appends a row with all check cells `pending` and a link to `runs/<date>/notes.md`; creates that file from a template (headings R1-R4, each with result, evidence paths, notes). Refuses if a row for that date and trigger exists. Subcommand `set <date> <check> <value>` updates one cell (`R1`, `R2`, `R3-T1`, `R3-T3`, `R4`, `Result`) with value in {pass, fail, skip, pending}.
5. `tests/unit/regression/test_new_entry.py`: create in a tmp root; row format matches the header column count; duplicate refused; `set` changes only the target cell; invalid value rejected.

## Acceptance criteria

- [ ] ROUTINE.md can be followed without this task file.
- [ ] ROUTINE.md can be followed without this task file. (Reviewer check; not ticked by the implementer.)
- [x] `new_entry` and `set` work as specified, with tests. Evidence: 26 passed in `tests/unit/regression/test_new_entry.py`.
- [x] LOG.md table header matches the plan. Evidence: `test_committed_header_matches_plan` passes against the committed `tests/regression/LOG.md`.

## Verification

```bash
pytest tests/unit/regression/test_new_entry.py -q
python -m tests.regression.new_entry --help
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/test-015-write-the-post-update-regression-routine worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-015
- 2026-11-22 [claude-agent] Added tests/regression/{__init__.py,LOG.md,ROUTINE.md,new_entry.py} and tests/unit/regression/test_new_entry.py. Verification: pytest test_new_entry.py 26 passed; --help exit 0; ruff, ruff format, mypy clean; full pytest 621 passed, 1 skipped. Acceptance 2 and 3 ticked; acceptance 1 left for reviewer.
- 2026-11-22 [claude-agent] Spec notes: RISK-005 docs call TEST-104 the routine owner; plan says TEST-015 writes routine and log, TEST-104 runs it first. Followed the plan; RISK-005 files not in touches, flagged for integrator. Used python instead of python3 for validate (no python3 here). set gained optional --trigger for dates with two rows.
- 2026-11-22 [claude-agent] Status in_progress -> review.
