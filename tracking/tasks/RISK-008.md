---
id: RISK-008
title: Risk review after Phase 5 (before scale-out and any publishing)
status: todo
phase: 5
area: RISK
kind: doc
plan_ref: "plans/detailed/07-risks-and-open-questions.md#risk-reviews"
depends_on: [RISK-007, GATE-P5]
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

Before scale-out, the risk register reflects Phases 4-5 (LiDAR accuracy, performance, placement method), and the Phase 6 decisions (DEC-011, DEC-001, DEC-010) have their evidence ready.

## Context

- Checklist: "Review checklist" in `tracking/logs/risk-reviews.md` (from RISK-006).
- Evidence: GATE-P4 and GATE-P5 notes; SCAN-101 accuracy report; TEST-103 reports; ADR-0004, ADR-0006, ADR-0008; `tracking/logs/sim-update-watch.md`; `docs/licenses/*`; `docs/compat/*`.
- Risks this review should move: R-04, R-06, R-07, R-10, R-11, R-13, R-14, R-15, R-16, R-18, R-20. Kill criteria K5, K6, K9 are the relevant ones.
- Phase 6 readiness: DEC-011 needs per-region hour actuals; DEC-001 needs RISK-001 and RISK-002 done; RISK-003 and RISK-004 outputs feed region masks.

## Steps

1. Run the review checklist for GATE-P5.
2. Update the register table in the detailed plan.
3. Check `docs/licenses/data-sources.md` and `docs/licenses/models-and-tools.md` check dates. If older than 6 months, flag that DEC-001 must re-verify terms.
4. Write a "Phase 6 readiness" list in the log entry: each of DEC-011, DEC-001, DEC-010, RISK-009 with evidence available (yes/no, path).
5. Append the dated entry to `tracking/logs/risk-reviews.md`, with a "FLAG FOR USER" block if needed.
6. Run `python3 scripts/tasks.py validate`.

## Acceptance criteria

- [ ] A dated GATE-P5 entry exists in `tracking/logs/risk-reviews.md`.
- [ ] Each listed risk has an outcome with an evidence link.
- [ ] K5, K6, K9 each have a status.
- [ ] The Phase 6 readiness list covers DEC-011, DEC-001, DEC-010 and RISK-009.

## Verification

```bash
grep -n "GATE-P5" tracking/logs/risk-reviews.md
grep -n "Phase 6 readiness" tracking/logs/risk-reviews.md
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
