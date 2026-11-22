---
id: LIVE-101
title: "Deliverable: palmlive live spawner (only if the Phase 5 bake-off picks live placement)"
status: todo
phase: 5
area: LIVE
kind: test
plan_ref: "plans/detailed/04-fs2024-integration.md#live-in-sim-validation"
depends_on: [LIVE-011, LIVE-100, ASSET-101, TEST-014, DEC-007]
requires: [windows-sim, human]
agent: simconnect-dotnet-engineer
estimate_h: 3
touches: [tests/perf/soak/, tracking/logs/LIVE-101.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

With real palm SimObjects, the live spawner survives a 1-hour soak flight within the cap, cleans up to zero on shutdown and after a forced kill, and has tuned radius and cap values. Other areas depend on this id as "live spawning works".

## Context

- Only if DEC-007 (ADR-0008, from the LIVE-009 bake-off) picked live placement; otherwise DEC-007 sets it to `dropped`.
- Soak report tooling and telemetry format: TEST-014 (`tests/perf/soak.py`, `plans/detailed/06-testing.md#soak-test`); use it for the counts CSV and the report.
- Plan section [LIVE in-sim validation](../../plans/detailed/04-fs2024-integration.md#live-in-sim-validation); soak requirement from `plans/06-testing.md` section 5 (count stays under cap, returns to zero after shutdown).
- SimObject titles from ASSET-101 must be in the region's index (rebuild with `palmgen index` after ASSET-101).

## Steps

1. Rebuild the live region (`--placement exclusions-only`) and `palmgen index`; activate it in PalmLive; start the sim; toggle Live palms.
2. Fly 1 hour mixing low passes (150-300 m) and street-level slews over the region; log live count and pending count every 10 s to `tests/perf/soak/<date>/counts.csv` (add a `--log-counts PATH` option to `spawn` only if missing; else use the window's count).
3. End with the toggle off: count 0, no palms visible near the aircraft.
4. Restart, toggle on, kill the App process from Task Manager, restart the App, run `cleanup`; confirm no leftovers (visual + count).
5. Tune `RadiusGroundM`, `RadiusHighM` and `MaxObjects` for no visible pop-in within the DEC-005 budget; record final values.
6. Write `tracking/logs/LIVE-101.md` with versions, max live count, cleanup results, tuned values, CPU/frametime notes.

## Acceptance criteria

- [ ] Live count ≤ cap for the whole hour.
- [ ] Zero objects after clean shutdown and after kill + `cleanup` (or the documented restart-required behaviour from SPIKE-005).
- [ ] Tuned values recorded.

## Verification

Manual on the Windows PC per the steps. Check: `python3 -c "import csv;r=list(csv.DictReader(open('tests/perf/soak/<date>/counts.csv')));print(max(int(x['live']) for x in r))"` ≤ cap; log file complete.

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Added depends_on TEST-014 (soak report tooling) and DEC-007 (live must be chosen in ADR-0008); ASSET-101 kept. Cross-area reconciliation.
