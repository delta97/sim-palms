---
id: REGION-014
title: "San Diego coastal: performance check over the densest area and region sign-off"
status: todo
phase: 6
area: REGION
kind: test
plan_ref: "plans/detailed/05-phases.md#per-region-task-pattern"
depends_on: [REGION-013]
requires: [windows-sim, gpu, human]
agent: test-engineer
estimate_h: 2
touches: [tests/perf/routes/region-san-diego-coastal/, tests/perf/runs/region-san-diego-coastal/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

The San Diego coastal package stays within the ADR-0006 performance budget over its densest palm area, and the region is signed off as active.

## Context

- Pattern and order: `plans/detailed/05-phases.md#per-region-task-pattern`. Commands: `docs/regions/RUNBOOK.md` (REGION-001).
- Region: **San Diego coastal**, file `regions/san-diego-coastal.yaml`, `id_prefix: sdc` (ARCH-008 wrote the starting file).
- If this region was the Phase 1-5 test region (it contains the DEC-004 block), most of this step was done before: review and update instead of starting over, and say so in the Log.
- If DEC-011 (ADR-0012) drops or reorders this region, set this task to `dropped` or adjust `depends_on`, and log why.
- Procedure: `tests/perf/PROCEDURE.md` (TEST-103). Comparison: `python -m tests.perf.compare` (`plans/detailed/06-testing.md#run-comparison`). Budget: ADR-0006.
- Variants: `nofix` and the chosen placement (`static` or `live`), 3 runs each, alternating.

## Steps

1. Find the densest 1 km cell with the RUNBOOK one-liner. Define a 5-minute low pass over it (150-300 m AGL) per PROCEDURE.md; save the route under `tests/perf/routes/region-san-diego-coastal/`.
2. Capture nofix r1, fix r1, nofix r2, fix r2, nofix r3, fix r3 into `tests/perf/runs/region-san-diego-coastal/<date>/captures/`.
3. `python -m tests.perf.compare tests/perf/runs/region-san-diego-coastal/<date>`. Exit 0 = within budget.
4. If over budget: record it, and propose a density cap or LOD change as a new task. Don't sign off.
5. Sign-off: add a Log line with build version, budget result, and the verdicts of the two earlier REGION tasks for this region.

## Acceptance criteria

- [ ] Route and 6 captures committed in the run layout (raw captures per `tests/perf/.gitignore`).
- [ ] `compare` exits 0 against the ADR-0006 budget.
- [ ] Sign-off line in the Log.

## Verification

```bash
python -m tests.perf.compare tests/perf/runs/region-san-diego-coastal/<date>
ls tests/perf/routes/region-san-diego-coastal/
```

## Log

- 2026-11-22 [plan-breakdown] Task created.
