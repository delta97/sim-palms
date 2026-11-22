---
id: RISK-007
title: Risk review after Phase 3 (mid-project)
status: todo
phase: 3
area: RISK
kind: doc
plan_ref: "plans/detailed/07-risks-and-open-questions.md#risk-reviews"
depends_on: [RISK-006, GATE-P3]
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

The risk register reflects Phases 1-3 evidence (detection quality, generator results, model quality, effort actuals), and every remaining DEC task is confirmed on time for its gate.

## Context

- Checklist: "Review checklist" section of `tracking/logs/risk-reviews.md` (written by RISK-006). Follow it exactly.
- Register, kill criteria and verification table: `plans/detailed/07-risks-and-open-questions.md`.
- Evidence to read: GATE-P1, GATE-P2, GATE-P3 notes; SCAN-100 `qa_summary.md`; GEN-100 `build_report.md`; ASSET-100 log; `tracking/logs/sim-update-watch.md`; ADR-0003, ADR-0007, ADR-0009, ADR-0010 if accepted.
- Risks this review should move: R-02, R-03, R-04, R-08, R-12, R-17, R-19, R-20, R-21. Kill criteria K2, K3, K4 are the relevant ones.
- Decisions to check for timing: DEC-005, DEC-007, DEC-003 (Phase 5), DEC-006 (before Phase 4 classifier work).

## Steps

1. Run the review checklist for GATE-P3.
2. Update the register table in the detailed plan (Lik./Impact, retired markers, new rows).
3. Record phase actual hours vs estimates for Phases 1-3 (R-20). If any phase exceeded its upper estimate by more than 50%, write a re-plan suggestion for the user.
4. Append the dated entry to `tracking/logs/risk-reviews.md`, with a "FLAG FOR USER" block if anything needs a decision.
5. Run `python3 scripts/tasks.py validate`.

## Acceptance criteria

- [ ] A dated GATE-P3 entry exists in `tracking/logs/risk-reviews.md`.
- [ ] Each listed risk has an outcome with an evidence link.
- [ ] K2, K3, K4 each have a status.
- [ ] Actual vs estimated hours for Phases 1-3 are recorded.

## Verification

```bash
grep -n "GATE-P3" tracking/logs/risk-reviews.md
grep -c "K[2-4]" tracking/logs/risk-reviews.md   # expect >= 3 more than after RISK-006
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
