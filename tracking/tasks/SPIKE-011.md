---
id: SPIKE-011
title: Write the Phase 0 go/no-go proposal and get the user's decision
status: todo
phase: 0
area: SPIKE
kind: decision
plan_ref: "plans/detailed/05-phases.md#phase-0-feasibility-spike"
depends_on: [SPIKE-010, RISK-005]
requires: [human]
agent: task-planner
estimate_h: 1
touches: [tracking/decisions/ADR-0014-phase-0-go-no-go.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

A written go/no-go decision on the Exclude TIN approach for the current sim update, proposed by an agent from the Phase 0 evidence and decided by the user, recorded as ADR-0014. GATE-P0 reads it.

## Context

- Decision point "after Phase 0: go / no-go on Exclude TIN; default: stop and file a bug report if exclusions don't work" (`plans/05-phases.md`, Decision points).
- Kill criterion K1 (`plans/detailed/07-risks-and-open-questions.md#kill-criteria`): pause if Exclude TIN or the vegetation exclude doesn't remove the blob on the current update.
- Evidence: `docs/findings/SPIKE-010.md` and the spike notes it links; RISK-005's watch log for open exclusion bugs.
- ADR numbers 0002-0012 are pre-assigned to DEC tasks and 0013 is taken. Use 0014; if taken, use the next free number and update `touches`.
- Procedure: same as every decision (`plans/detailed/07-risks-and-open-questions.md#how-every-decision-task-runs`). Agents propose; the user decides.

## Steps

1. Write `tracking/decisions/ADR-0014-phase-0-go-no-go.md` from `tracking/decisions/_TEMPLATE.md`, Status `proposed`, Task `SPIKE-011`.
2. Options:
   - **Go**: all three exit criteria met.
   - **Go with changes**: the cut works, but something changes the plan (for example builds can't run with the sim open, so the companion app only builds before launch; or SimConnect objects leak, so live placement starts as a long shot). List each change and the task or plan section it affects.
   - **Pause (K1)**: the cut does not work on this update. File or upvote a DevSupport bug (link it), keep all code, and let RISK-005 trigger a Phase 0 rerun on the next update.
3. Recommend one option, with one sentence per exit criterion pointing at its evidence.
4. Ask the user in one short message: options, recommendation, what changes downstream. Record the answer, the date and "Decided by: user". Set Status `accepted`.
5. If Pause: also list which Linux tasks may continue (ADR-0013) and which should stop.

## Acceptance criteria

- [ ] ADR-0014 exists with all three options, a recommendation and links to evidence.
- [ ] Status `accepted` and Decided by the user (a provisional default is not allowed for this decision: if the user is unavailable, the task stays in `review`).
- [ ] Downstream changes (if any) are listed with task ids.

## Verification

```bash
grep -E "Status:\*\* accepted" tracking/decisions/ADR-0014-phase-0-go-no-go.md
grep -c "SPIKE-0" tracking/decisions/ADR-0014-phase-0-go-no-go.md
```

## Log

- 2026-11-22 [plan-breakdown] Task created.
