---
id: REGION-001
title: Write the per-region scale-out runbook (commands for each region step)
status: todo
phase: 6
area: REGION
kind: doc
plan_ref: "plans/detailed/05-phases.md#per-region-task-pattern"
depends_on: [GATE-P5]
requires: [none]
agent: geo-data-engineer
estimate_h: 2
touches: [docs/regions/RUNBOOK.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

`docs/regions/RUNBOOK.md` gives the exact commands for the five per-region steps (config, masks, palmscan + QA, palmgen build + spot checks, perf check), using the tools as they exist after Phase 5. Every REGION task follows it, so a new region is a copy-and-fill job.

## Context

- Pattern: `plans/detailed/05-phases.md#per-region-task-pattern`.
- Tools and flags: `palmscan` (`plans/detailed/02-detection-pipeline.md#cli`), `palmgen` (`plans/detailed/04-fs2024-integration.md#palmgen-cli`), `palmlive` region manager (LIVE-100), visual protocol (`tests/visual/PROTOCOL.md`), perf procedure (`tests/perf/PROCEDURE.md`), build checker (`tests/regression/check_build.py`), contract checker (`tests/helpers/contract.py`).
- The placement method is fixed by ADR-0008 (DEC-007). Static: one `palmgen build`. Live: `palmgen build --placement exclusions-only` plus `palmgen index`.
- Write commands from the merged code and `--help` output, not from the plans. Where they differ, the code wins; note the difference.

## Steps

1. Run each tool's `--help` and note the real flags.
2. Write `docs/regions/RUNBOOK.md` with sections: Summary; Before you start (inputs: DEC-011 list, `docs/compat/*`, ADR-0008); Step 1 config; Step 2 masks; Step 3 palmscan + QA; Step 4 build + 3 spot checks; Step 5 perf over the densest area; Step 6 sign-off (what to log, how to activate in palmlive); Creating the tasks for a new region (`python3 scripts/tasks.py new REGION --title "..." --phase 6`, ids `REGION-0N0..0N4`); Recap.
3. Include the two helper one-liners:
   - three random spot-check palms, seeded by the region name, from `data/<region>/palms.geojson`;
   - the densest 1 km grid cell (palm count per cell) for the perf route.
4. Test both one-liners on the test region's `palms.geojson` and paste their output into the Log.

## Acceptance criteria

- [ ] RUNBOOK.md covers all six steps with copy-paste commands and placeholders `<region>`, `<date>`.
- [ ] Both one-liners run on a real `palms.geojson` (output in the Log).
- [ ] Every command was checked against `--help` of the merged tools.

## Verification

```bash
test -f docs/regions/RUNBOOK.md && grep -cE "^## " docs/regions/RUNBOOK.md    # expect >= 8
python -m palmscan run --help && python -m palmgen build --help
```

## Log

- 2026-11-22 [plan-breakdown] Task created.
