---
id: GATE-P2
title: "Phase 2 exit gate: generated package removes the test neighbourhood's blobs"
status: todo
phase: 2
area: GATE
kind: gate
plan_ref: "plans/detailed/05-phases.md#phase-2-generator-mvp"
depends_on: [GATE-P1, GEN-012, GEN-100, TEST-002, TEST-007, TEST-016, TEST-102, TEST-104]
requires: [human]
agent: task-planner
estimate_h: 0.5
touches: []
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

The user confirms that `palmgen build --region <test>` makes a Community package that removes the test neighbourhood's palm blobs, drops in stand-in trees, and doesn't cut buildings or let autogen trees into the holes. Passing starts the palm model work (ASSET-010 depends on this gate).

## Context

- Exit criteria: `plans/05-phases.md` Phase 2; breakdown `plans/detailed/05-phases.md#phase-2-generator-mvp`.
- Test gating: golden files, build checks, in-sim visual at T1 and T3, regression baseline (`plans/detailed/06-testing.md#which-tests-gate-which-phase`). Checklist ids C1-C8: `plans/detailed/06-testing.md#visual-run-format`.
- Kill criteria K2 and K3 (`plans/detailed/07-risks-and-open-questions.md#kill-criteria`).
- Sign-off: the user.

## Steps

1. Check every `depends_on` task is `done`.
2. Fill in the Evidence list.
3. Review GEN-100's T1 and T3 runs side by side (no-fix vs fix) with the user; count visible blobs before and after at T1.
4. User decides pass or fail. Pass: `python3 scripts/tasks.py set GATE-P2 done --by user --note "<% blobs gone>"`.

## Acceptance criteria

- [ ] At least 90% of the palm blobs visible in the T1 no-fix screenshots are gone in the fix screenshots (count recorded in `tracking/logs/GEN-100.md`).
- [ ] T1 and T3 visual runs: checklist C1 (blobs gone), C4 (no walls cut) and C5 (no autogen trees in holes) pass at VP1, VP2 and VP3 (`check_run` result `pass` in `tests/visual/test_log.md`).
- [ ] C6 (ground under cuts acceptable) is not `fail` at any T1 viewpoint, i.e. the cut looks better than the blob (K2).
- [ ] Golden XML tests pass in CI (`pytest tests/unit/palmgen -q`).
- [ ] `python -m tests.regression.check_build build/palmfix-<test> --palms <palms.geojson>` exits 0 (counts match, one BGL per tile).
- [ ] The no-fix baseline exists at T1-T5 (TEST-007) and the regression log has a baseline row (TEST-104).
- [ ] The chosen `exclusion.margin_m` is in the test region YAML (GEN-017).

## Evidence

- GEN-100 log: `tracking/logs/GEN-100.md`
- Margin tuning: `tracking/logs/GEN-017.md`
- T1 run folder: `tests/visual/T1/<date>_<label>/`
- T3 run folder: `tests/visual/T3/<date>_<label>/`
- Baseline runs: `tests/visual/test_log.md` (TEST-007 rows)
- Regression baseline: `tests/regression/LOG.md`
- Build report: `build/palmfix-<test>/build_report.md` (paste key counts into the log)
- CI run with golden tests:

## On fail

- **No margin gives a cut that looks better than the blob at all three viewpoints (K2):** stop after Phase 2. Write findings into this Log and `docs/findings/`. The project does not go on to assets.
- **Cuts damage buildings at T3 even with clipping (K3):** limit the fix to palms with `building_conflict = false`. If that leaves under 70% of T1 blobs fixed, treat as K2.
- **Under 90% of blobs gone, but no K2/K3:** look for the cause (missing palms → back to SCAN; radius too small → GEN-017; tile or build errors → GEN-016), fix, rerun GEN-100 and this gate.
- **Autogen trees in holes:** check the vegetation exclude flag in the generated XML against `captured/scene_one_polygon.xml`; fix the template (GEN-009) and rerun.

## Verification

```bash
python3 scripts/tasks.py show GATE-P2
grep -E "T1|T3" tests/visual/test_log.md
grep -i "baseline" tests/regression/LOG.md
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
