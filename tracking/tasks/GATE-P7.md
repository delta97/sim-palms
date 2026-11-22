---
id: GATE-P7
title: "Phase 7 exit gate: offline image-layer go/no-go accepted"
status: todo
phase: 7
area: GATE
kind: gate
plan_ref: "plans/detailed/05-phases.md#phase-7-image-layer-experiment"
depends_on: [FX-100]
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

The user accepts the Stage A (offline) image-layer result as GO or NO-GO against the criteria fixed in advance. GO makes the Stage B real-time tasks workable; NO-GO ends Phase 7 and the scenery fix stays the answer.

## Context

- Phase 7 is optional (`plans/05-phases.md`). If the user skips it, set this gate and the FX tasks to `dropped`.
- Criteria C0-C4 and the GO/NO-GO labels: `plans/detailed/08-image-layer-experiment.md#stage-a-go-or-no-go-criteria`. Thresholds are fixed before judging and can't change after seeing results.
- Stage B tasks (FX-021..FX-025) depend on FX-100 directly; they are not part of this gate.
- Kill criterion K8 (`plans/detailed/07-risks-and-open-questions.md#kill-criteria`).
- Optional image-diff scoring (TEST-008) may support the report; it does not gate.
- Sign-off: the user.

## Steps

1. Check FX-100 is `done`.
2. Read `palmfx/docs/stage-a-report.md` with the user: one row per criterion, measured value, pass or fail.
3. User accepts GO or NO-GO. Pass the gate either way once the verdict is accepted: `python3 scripts/tasks.py set GATE-P7 done --by user --note "<GO|NO-GO-Cn>"`.
4. On NO-GO: set FX-021..FX-025 to `dropped` with the note `NO-GO-Cn (GATE-P7)`.

## Acceptance criteria

- [ ] The report states the chosen configuration (mask method, backend, variant) and the measured value for each of C0-C4.
- [ ] Thresholds in the report match plan 08 unchanged (or the run is labelled as a separate run).
- [ ] The verdict (GO or NO-GO with its first failing criterion) is accepted by the user.
- [ ] On NO-GO, Stage B tasks are `dropped`.

## Evidence

- Report: `palmfx/docs/stage-a-report.md`
- Judging results: `palmfx/docs/judging/`
- Run log: `palmfx/docs/stage-a-runlog.md`
- Depth access verdict: `palmfx/docs/depth-access.md`

## On fail

The gate itself doesn't fail on NO-GO: NO-GO is a valid outcome (K8 stops Phase 7). The gate fails only if the report is incomplete or thresholds were changed after judging; then FX-100 goes back to `in_progress`.

## Verification

```bash
grep -E "GO|NO-GO" palmfx/docs/stage-a-report.md
python3 scripts/tasks.py list --area FX --status todo
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
