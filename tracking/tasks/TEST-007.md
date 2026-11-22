---
id: TEST-007
title: Capture a baseline no-fix visual run at T1-T5
status: todo
phase: 2
area: TEST
kind: test
plan_ref: "plans/detailed/06-testing.md#visual-protocol"
depends_on: [TEST-100, TEST-102]
requires: [windows-sim, human]
agent: test-engineer
estimate_h: 3
touches: [tests/visual/T1/, tests/visual/T2/, tests/visual/T3/, tests/visual/T4/, tests/visual/T5/, tests/visual/test_log.md, tests/visual/graphics_profile.yaml]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

A committed set of no-fix screenshots at all three viewpoints of every test site, on a recorded sim version and graphics profile. Later runs, sim updates and the image-diff score compare against it.

## Context

- Procedure: `tests/visual/PROTOCOL.md` (TEST-102). Viewpoint recall: `tests/sites/<site>/` and `docs/findings/TEST-006.md`.
- No palmfix package exists yet (or deactivate it). Variant is `nofix` only.
- This run fills in `graphics_profile.yaml` `ref-v1` with the user's real settings. Those settings are then fixed for every later run.

## Steps

1. On the sim PC, record the current graphics settings into `tests/visual/graphics_profile.yaml` profile `ref-v1` (replace every `TBD`).
2. Make sure no palmfix package is in the Community folder.
3. For each site T1-T5: `python -m tests.visual.new_run --site <T> --label baseline --variants nofix --sim-version <v> --tester <name>`.
4. Load the site flight, recall VP1, VP2, VP3 in order, take one screenshot each, copy into `raw/nofix/`.
5. `python -m tests.visual.new_run finalize <run_dir>`; check the printed mapping.
6. Checklist: for a baseline only C1 matters, and it is expected to fail where blobs exist (that's the point). Fill C1 with `fail` where blobs are visible, `pass` where not (T5), and the rest `na`. Note blob counts per viewpoint in Notes.
7. `python -m tests.visual.check_run <run_dir> --update-log`. Expect `fail` for T1-T4 (blobs present) and `pass` for T5; this is correct for a baseline. Write "baseline" in the Notes.

## Acceptance criteria

- [ ] Five run folders, each with three finalized JPEGs and a filled checklist.
- [ ] `graphics_profile.yaml` `ref-v1` has no `TBD` values.
- [ ] `test_log.md` has five baseline rows with sim version.

## Verification

```bash
for s in T1 T2 T3 T4 T5; do ls tests/visual/$s/*_baseline/nofix/; done   # 3 JPEGs each
grep -c baseline tests/visual/test_log.md   # 5
! grep -q TBD tests/visual/graphics_profile.yaml && echo "profile filled"
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
