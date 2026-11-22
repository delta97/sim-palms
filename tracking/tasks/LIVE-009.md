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
touches: [tests/perf/bakeoff/, docs/findings/LIVE-009.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Static and live palm placement are measured against no-fix on the same flight, and the measurements plus a recommendation from the plan's decision rule are written to `docs/findings/LIVE-009.md`. DEC-007 turns that into the decision (ADR-0008); GATE-P5 reads both.

## Context

- Procedure and decision rule: plan section [LIVE placement bake-off](../../plans/detailed/04-fs2024-integration.md#live-placement-bake-off); performance method in `plans/06-testing.md` section 5 and TEST-103's harness; budget and reference settings from DEC-005.
- Both fix setups use exclusions from the region package. Default to static when results are close (plan 05).
- This task does not decide or drop tasks. DEC-007 (depends on this task) writes ADR-0008 and drops LIVE-010, LIVE-011, LIVE-101 and ASSET-101 if static wins.

## Steps

1. Build both packages: `palmgen build --region <dense> --placement static --models library --out build/bakeoff-static`; `palmgen build --region <dense> --placement exclusions-only --out build/bakeoff-live` then `palmgen index --region <dense> --out build/bakeoff-live`.
2. Setup A no fix: no palmfix region linked. Setup B static: link via `PalmLive.App --build-root build/bakeoff-static regions only <dense>`. Setup C live: link the live build and run `PalmLive.App --build-root build/bakeoff-live spawn`.
3. Run TEST-103's fixed flight 3 times per setup, same settings; restart the sim between setups.
4. Collect average FPS, 1% low, p99 frametime, stutter events, live object count (C), and visual notes (pop-in at the spawn edge, LOD transitions) into `tests/perf/bakeoff/<date>/report.md` with raw captures alongside.
5. Apply the decision rule as a recommendation; write `docs/findings/LIVE-009.md` (setups, versions, settings, measurements table per setup and run, visual notes, rule applied, recommendation, link to `tests/perf/bakeoff/<date>/`). Hand over to DEC-007.

## Acceptance criteria

- [ ] 9 runs captured (3 × 3) with raw files.
- [ ] Report table compares all metrics against DEC-005's budget.
- [ ] `docs/findings/LIVE-009.md` states the rule applied and the recommendation, with numbers.
- [ ] No ADR written here (DEC-007 writes ADR-0008).

## Verification

Manual: `tests/perf/bakeoff/<date>/report.md` exists with a 3-setup × 4-metric table and per-run values; `docs/findings/LIVE-009.md` summarises them with the recommendation.

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Bake-off now only measures: results go to docs/findings/LIVE-009.md (plus raw runs under tests/perf/bakeoff/), not tracking/decisions/ADR-placement-bakeoff.md. DEC-007 depends on this task and writes ADR-0008 and drops/keeps follow-up tasks. Cross-area reconciliation.
