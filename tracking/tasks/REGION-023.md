---
id: REGION-023
title: "LA Westside and beaches: palmgen build and spot checks at three random locations"
status: todo
phase: 6
area: REGION
kind: test
plan_ref: "plans/detailed/05-phases.md#per-region-task-pattern"
depends_on: [REGION-022, REGION-014]
requires: [windows-sim, human]
agent: msfs-sdk-specialist
estimate_h: 2.5
touches: [tests/visual/regions/la-westside/, tracking/logs/REGION-023.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

The LA Westside and beaches package builds cleanly, activates through palmlive, and looks right at three randomly chosen palm locations.

## Context

- Pattern and order: `plans/detailed/05-phases.md#per-region-task-pattern`. Commands: `docs/regions/RUNBOOK.md` (REGION-001).
- Region: **LA Westside and beaches**, file `regions/la-westside.yaml`, `id_prefix: law` (ARCH-008 wrote the starting file).
- If this region was the Phase 1-5 test region (it contains the DEC-004 block), most of this step was done before: review and update instead of starting over, and say so in the Log.
- If DEC-011 (ADR-0012) drops or reorders this region, set this task to `dropped` or adjust `depends_on`, and log why.
- Placement per ADR-0008: static → `palmgen build`; live → `palmgen build --placement exclusions-only` and `palmgen index`, then the live spawner.
- Spot checks use the visual checklist C1-C8 (`plans/detailed/06-testing.md#visual-run-format`) at street level and 150 m. If `tests.visual.new_run` only accepts registered sites, use the same folder layout by hand (VERIFY in the RUNBOOK).
- The sim PC is shared by every windows-sim task: batch this with the perf check if possible.

## Steps

1. `palmgen build --region la-westside` (placement per ADR-0008). Then `python -m tests.regression.check_build build/palmfix-la-westside --palms data/la-westside/palms.geojson --append-history` exits 0. Note build time and tile count.
2. Activate the region in palmlive. Start the sim.
3. Pick three random palms with the seeded one-liner from RUNBOOK.md. Record their `palm_id` and lon/lat.
4. At each: no-fix and fix screenshots at street level and 150 m into `tests/visual/regions/la-westside/<date>/spot-<n>/<variant>/`; fill a checklist (C1-C8) per spot.
5. Note any blob without a palm record and any palm without a blob (R-05).
6. Write `tracking/logs/REGION-023.md`: build numbers, spot table (spot × checklist), issues, verdict.

## Acceptance criteria

- [ ] `check_build` exits 0.
- [ ] Three spots, each with no-fix and fix screenshots at two heights and a filled checklist.
- [ ] No `fail` in C1, C4 or C5 at any spot, or the failure has a follow-up task.

## Verification

```bash
ls tests/visual/regions/la-westside/
grep -iE "verdict|spot" tracking/logs/REGION-023.md
```

## Log

- 2026-11-22 [plan-breakdown] Task created.
