---
id: LIVE-009
title: "Static vs live placement bake-off"
status: todo
phase: 5
area: LIVE
kind: test
plan_ref: "plans/detailed/04-fs2024-integration.md#live-placement-bake-off"
depends_on: [LIVE-008, GEN-019, ASSET-101, TEST-103, DEC-005]
requires: [windows-sim, gpu, human]
agent: simconnect-dotnet-engineer
estimate_h: 5
touches: [tests/perf/bakeoff/, tracking/decisions/ADR-placement-bakeoff.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Static and live palm placement are measured against no-fix on the same flight, and a written decision picks one, with numbers. GATE-P5 reads it.

## Context

- Procedure and decision rule: plan section [LIVE placement bake-off](../../plans/detailed/04-fs2024-integration.md#live-placement-bake-off); performance method in `plans/06-testing.md` section 5 and TEST-103's harness; budget and reference settings from DEC-005.
- Both fix setups use exclusions from the region package. Default to static when results are close (plan 05).
- If static wins, set LIVE-010, LIVE-011 and LIVE-101 to `dropped` with a note pointing at the ADR.

## Steps

1. Build both packages: `palmgen build --region <dense> --placement static --models library --out build/bakeoff-static`; `palmgen build --region <dense> --placement exclusions-only --out build/bakeoff-live` then `palmgen index --region <dense> --out build/bakeoff-live`.
2. Setup A no fix: no palmfix region linked. Setup B static: link via `PalmLive.App --build-root build/bakeoff-static regions only <dense>`. Setup C live: link the live build and run `PalmLive.App --build-root build/bakeoff-live spawn`.
3. Run TEST-103's fixed flight 3 times per setup, same settings; restart the sim between setups.
4. Collect average FPS, 1% low, p99 frametime, stutter events, live object count (C), and visual notes (pop-in at the spawn edge, LOD transitions) into `tests/perf/bakeoff/<date>/report.md` with raw captures alongside.
5. Apply the decision rule; write `tracking/decisions/ADR-placement-bakeoff.md` (context, options, measurements table, decision, consequences).

## Acceptance criteria

- [ ] 9 runs captured (3 × 3) with raw files.
- [ ] Report table compares all metrics against DEC-005's budget.
- [ ] ADR states the decision and the rule applied.
- [ ] Follow-up tasks dropped or kept accordingly.

## Verification

Manual: `tests/perf/bakeoff/<date>/report.md` exists with a 3-setup × 4-metric table and per-run values; `tracking/decisions/ADR-placement-bakeoff.md` records the decision. `python3 scripts/tasks.py show LIVE-010` reflects it.

## Log

- 2026-11-21 [plan-breakdown] Task created.
