---
id: GATE-P6
title: "Phase 6 exit gate: first two regions packaged, checked and within budget"
status: todo
phase: 6
area: GATE
kind: gate
plan_ref: "plans/detailed/05-phases.md#phase-6-scale-out"
depends_on: [GATE-P5, DEC-011, REGION-001, REGION-010, REGION-011, REGION-012, REGION-013, REGION-014, REGION-020, REGION-021, REGION-022, REGION-023, REGION-024, DEC-001, DEC-010, RISK-009]
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

The user confirms that scale-out works: San Diego coastal and LA Westside and beaches (or the first two regions in ADR-0012) are built, checked and within the performance budget, and the publish-or-personal decision is made. After this gate the per-region pattern is repeated for later regions (REGION-030, 040, 050).

## Context

- Phase 6 in `plans/05-phases.md`; breakdown and per-region pattern `plans/detailed/05-phases.md#phase-6-scale-out`.
- Test gating per region: contract conformance, spot-check visual, perf over the densest area, regression routine (`plans/detailed/06-testing.md#which-tests-gate-which-phase`).
- Decision point after Phase 6: publish or keep personal (default personal until licenses are checked). If DEC-001 says personal, DEC-010 and RISK-009 are `dropped`, which counts as satisfied.
- If ADR-0012 drops or swaps a region, its tasks are `dropped` or renamed; this gate then checks whatever two regions came first.
- Kill criterion K7 (`plans/detailed/07-risks-and-open-questions.md#kill-criteria`) applies to publishing only.
- Sign-off: the user.

## Steps

1. Check every `depends_on` task is `done` or `dropped`.
2. Fill in the Evidence list, one block per region.
3. Review each region's QA verdict, spot checks and perf result with the user.
4. User decides. Pass: `python3 scripts/tasks.py set GATE-P6 done --by user`.

## Acceptance criteria

Per region (San Diego coastal, LA Westside and beaches):

- [ ] `palms.geojson` passes the contract check and the QA log verdict is "ok" or "ok with notes" (REGION-012 / REGION-022).
- [ ] `check_build` exits 0 and three random spot checks have no `fail` in C1, C4 or C5 (REGION-013 / REGION-023).
- [ ] `tests.perf.compare` exits 0 against the ADR-0006 budget over the densest area (REGION-014 / REGION-024).
- [ ] `mask_out` covers every installed overlapping mod and airport add-on; no doubled palms in the spot checks (R-13).
- [ ] Regions don't overlap, or mask each other out.

Overall:

- [ ] ADR-0012 (regions and Florida) and ADR-0002 (personal or publish) are `accepted`.
- [ ] If publishing: ADR-0011 accepted and `docs/licenses/ATTRIBUTION.md` written; nothing is uploaded before both.

## Evidence

- Runbook: `docs/regions/RUNBOOK.md`
- San Diego coastal: `tracking/logs/REGION-012-qa.md`, `tracking/logs/REGION-013.md`, `tests/visual/regions/san-diego-coastal/`, `tests/perf/runs/region-san-diego-coastal/`
- LA Westside: `tracking/logs/REGION-022-qa.md`, `tracking/logs/REGION-023.md`, `tests/visual/regions/la-westside/`, `tests/perf/runs/region-la-westside/`
- Decisions: `tracking/decisions/ADR-0012-scale-out-regions.md`, `tracking/decisions/ADR-0002-personal-or-publish.md`, `tracking/decisions/ADR-0011-data-redistribution.md`
- Actual hours per region (from task logs):

## On fail

- **A region is over budget:** cap density or shrink the region (new task), rerun the perf check. Don't pass with a region over budget.
- **Spot checks fail:** fix the cause (data → REGION-x2, cut or placement → GEN, masks → REGION-x1), rerun the spot check.
- **A license blocks redistribution (K7):** stop publishing that part (tools only, or personal). The project continues; this gate can still pass for personal use.
- **Per-region hours are far over 10 h:** record actuals; ask the user whether to continue with REGION-030/040/050 or stop here.

## Verification

```bash
python3 scripts/tasks.py list --area REGION
grep -iE "verdict" tracking/logs/REGION-012-qa.md tracking/logs/REGION-022-qa.md
python3 scripts/tasks.py show GATE-P6
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
