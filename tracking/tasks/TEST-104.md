---
id: TEST-104
title: Run the post-update regression routine once and record the baseline log entry
status: todo
phase: 2
area: TEST
kind: test
plan_ref: "plans/detailed/06-testing.md#regression"
depends_on: [TEST-015, TEST-016, TEST-007, GEN-100, GATE-P0]
requires: [windows-sim, human]
agent: msfs-sdk-specialist
estimate_h: 3
touches: [tests/regression/LOG.md, tests/regression/runs/, tests/regression/build_history.csv, tests/visual/T1/, tests/visual/T3/, tests/visual/test_log.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

The regression routine has been run end to end once on the current sim and SDK, so the log has a known-good baseline row and the routine is proven to work before the first real sim update.

## Context

- Procedure: `tests/regression/ROUTINE.md` (TEST-015). Tools: `new_entry`, `check_build` (TEST-016), visual protocol (TEST-102).
- Needs a working region package (GEN-100) and the Phase 0 single-blob project (GATE-P0 passed).
- VERIFY (V11): the path of the Phase 0 single-blob project. Look in `docs/findings/` and `plans/detailed/05-phases.md`. If it's not in the repo, ask the user where it is and record the path in ROUTINE.md.
- Use trigger `SDK` or `SU` with the current versions; note "baseline" in the notes file.
- Each later sim update repeats this routine as its own new task (`python3 scripts/tasks.py new TEST --title "Regression after SU<n>" --phase <current>`).

## Steps

1. `python -m tests.regression.new_entry --trigger SU --sim-version <v> --sdk-version <v>`.
2. R1: build and view the Phase 0 single-blob project; record pass/fail and two screenshots' paths in `runs/<date>/notes.md`.
3. R2: `palmgen build --region <T1 region>`; then `python -m tests.regression.check_build build/palmfix-<region> --palms <palms.geojson> --append-history`.
4. R3: visual protocol at T1 and T3 with `--label regression --variants nofix,static`; `check_run --update-log`.
5. R4: `skip` unless R1-R3 had a failure.
6. Fill the row with `new_entry set ...`; set `Result`.
7. Note in ROUTINE.md any step that was unclear or slow, and fix the wording.

## Acceptance criteria

- [ ] LOG.md has a complete baseline row (no `pending`).
- [ ] `runs/<date>/notes.md` has evidence for R1-R3.
- [ ] Visual run folders for T1 and T3 exist and are in `test_log.md`.
- [ ] Phase 0 project path recorded in ROUTINE.md (V11).

## Verification

```bash
grep -v pending tests/regression/LOG.md | tail -n 1
tail -n 1 tests/regression/build_history.csv
python -m tests.visual.check_run tests/visual/T1/<date>_regression; echo "exit=$?"
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-21 [plan-breakdown] Task created.
