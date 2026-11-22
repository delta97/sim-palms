---
id: GATE-P3
title: "Phase 3 exit gate: five SoCal species accepted and used in the region package"
status: todo
phase: 3
area: GATE
kind: gate
plan_ref: "plans/detailed/05-phases.md#phase-3-palm-asset-library"
depends_on: [GATE-P2, DEC-002, DEC-008, RISK-002, ASSET-016, ASSET-023, ASSET-033, ASSET-043, ASSET-053, ASSET-100, GEN-019]
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

The user confirms that real palm models replace the stand-ins: each of the five SoCal species passes its acceptance review, `palmfix-assets` 1.0.0 is built, and the test neighbourhood looks right at street level, 150 m and 600 m with the real models.

## Context

- Exit criteria: `plans/05-phases.md` Phase 3; acceptance checklist `plans/detailed/03-palm-assets.md#w11-acceptance-review`; breakdown `plans/detailed/05-phases.md#phase-3-palm-asset-library`.
- Test gating: in-sim visual at T1, where C3, C7 and C8 now apply (`plans/detailed/06-testing.md#which-tests-gate-which-phase`).
- Viewpoint mismatch: plan 03 uses 600 m, plan 06 VP3 uses 500 m. Until resolved (Open questions in the detailed phase plan), accept the 500 m VP3 if the 600 m lineup screenshots from the species reviews also pass.
- Kill criterion K4 (`plans/detailed/07-risks-and-open-questions.md#kill-criteria`).
- After a pass, RISK-007 (mid-project risk review) becomes ready.
- Sign-off: the user.

## Steps

1. Check every `depends_on` task is `done`.
2. Fill in the Evidence list.
3. With the user, look at each species review and the GEN-019 T1 run.
4. User decides. Pass: `python3 scripts/tasks.py set GATE-P3 done --by user`.

## Acceptance criteria

- [ ] Each species has `status: accepted` in `assets/species/<key>.yaml` and a filled review in `assets/reviews/<key>.md`: washingtonia_robusta, washingtonia_filifera, phoenix_canariensis, syagrus_romanzoffiana, archontophoenix_cunninghamiana.
- [ ] Every review checklist item passes: automated checks (zero errors), right at street level / 150 m / 600 m at noon and golden hour, base on the ground, no distracting LOD pop, matches reference photos, within LOD budget.
- [ ] `palmfix-assets` 1.0.0 builds and `assets/manifest.json` lists every variant with its GUID (ASSET-100).
- [ ] The test region package built with `--models library` places real models (GEN-019): T1 checklist passes at VP1-VP3 with C2, C3, C7 and C8 no longer `na`.
- [ ] ADR-0003 (build or license) and ADR-0009 (binary storage) are accepted, and the model license audit has no blocker for personal use (RISK-002).

## Evidence

- Species reviews: `assets/reviews/*.md`
- Lineup screenshots: `tests/visual/lineup-<species>/`
- GEN-019 log and T1 run: `tracking/logs/GEN-019.md`, `tests/visual/T1/<date>_<label>/`
- Asset package and manifest: `assets/manifest.json`, ASSET-100 log
- Decisions: `tracking/decisions/ADR-0003-build-or-license-models.md`, `tracking/decisions/ADR-0009-asset-binary-storage.md`
- Actual hours per species (from task logs), for DEC-006 and RISK-007:

## On fail

- **First species (Mexican fan palm) fails acceptance after two revision rounds and licensing is not viable (K4):** stop Phase 3. Revisit DEC-002 once. If still failing, stop the project at the Phase 2 output (exclusions with stand-ins) as a personal experiment.
- **One later species fails:** fix inside its review task (small fixes) or add a fix task. Option: ship four species and map the failing one to the closest accepted model with `species_fallback`, if the user agrees.
- **Models look right in the lineup but wrong at T1 (floating, wrong scale):** GEN-019 issue (scale, heading, ground snap); fix and rerun GEN-019.

## Verification

```bash
grep -l "status: accepted" assets/species/*.yaml | wc -l    # expect 5
python -m palmcore.assets check
python3 scripts/tasks.py show GATE-P3
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
