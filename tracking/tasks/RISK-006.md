---
id: RISK-006
title: Define the risk review routine and run the first review after Phase 0
status: todo
phase: 0
area: RISK
kind: doc
plan_ref: "plans/detailed/07-risks-and-open-questions.md#risk-reviews"
depends_on: [GATE-P0]
requires: [none]
agent: task-planner
estimate_h: 2
touches: [plans/detailed/07-risks-and-open-questions.md, tracking/logs/risk-reviews.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

The risk register is re-rated with what Phase 0 actually found, and a reusable review checklist exists in `tracking/logs/risk-reviews.md` so RISK-007 and RISK-008 repeat the same steps.

## Context

- Register, kill criteria, decision register and verification table: `plans/detailed/07-risks-and-open-questions.md`.
- Phase 0 evidence: GATE-P0 result, SPIKE-003 (templates, what is left under a cut, building cut test), SPIKE-004 (build times, sim-open behaviour), SPIKE-005 (SimConnect object after disconnect), RISK-005 watch log.
- Risks Phase 0 should move: R-01, R-02, R-03, R-08, R-09, R-11.
- This is doc work. Re-ratings that trigger a kill criterion must be flagged to the user, not acted on.

## Steps

1. Create `tracking/logs/risk-reviews.md` with a "Review checklist" section:
   1. Read task logs and gate notes since the last review, and `tracking/logs/sim-update-watch.md`.
   2. For each R-row: keep, re-rate (old → new likelihood/impact, with evidence link), retire (evidence per the verification table), or add a new row.
   3. Check each kill criterion K1-K9: not triggered / triggered (then flag to the user).
   4. Check each open DEC task: is it on time for its "needed by" gate? List any at risk.
   5. Record actual vs estimated hours for the finished phase (R-20).
   6. Append a dated entry: date, gate, changes, flags for the user.
2. Run the checklist for Phase 0.
3. Edit the risk register table in the detailed plan: update Lik./Impact cells and add rows if needed. Retired rows stay with "(retired YYYY-MM-DD, see risk-reviews log)" in the Risk cell.
4. If any kill criterion is triggered, write it at the top of the log entry under "FLAG FOR USER".
5. Run `python3 scripts/tasks.py validate`.

## Acceptance criteria

- [ ] `tracking/logs/risk-reviews.md` has the checklist and one dated entry for GATE-P0.
- [ ] R-01, R-02, R-03, R-08, R-09 and R-11 each have an explicit outcome (kept, re-rated or retired) with an evidence link.
- [ ] Kill criteria K1-K9 each have a status in the entry.
- [ ] The decision register has no overdue DEC without a flag.

## Verification

```bash
grep -n "Review checklist" tracking/logs/risk-reviews.md
grep -c "R-0[1-9]" tracking/logs/risk-reviews.md     # expect >= 6
grep -c "K[1-9]" tracking/logs/risk-reviews.md       # expect >= 9
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
