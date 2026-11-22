---
id: LIVE-100
title: "Deliverable: palmlive region manager (list, activate, deactivate via folder links)"
status: todo
phase: 5
area: LIVE
kind: test
plan_ref: "plans/detailed/04-fs2024-integration.md#live-in-sim-validation"
depends_on: [LIVE-005, GEN-100]
requires: [windows-sim, human]
agent: simconnect-dotnet-engineer
estimate_h: 2
touches: [palmlive/PalmLive.Core/Sim/ProcessSimDetector.cs, tests/fixtures/palmlive/plans/real_export.pln, tracking/logs/LIVE-100.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

On the Windows PC, the PalmLive window switches a real region package on and off with one click via a junction, MSFS 2024 loads it from the link, the sim-running banner works, and the build output is never harmed.

## Context

- Plan section [LIVE in-sim validation](../../plans/detailed/04-fs2024-integration.md#live-in-sim-validation). Phase 5 exit criterion: switching regions takes one click and needs no file copying.
- VERIFY here: MSFS 2024 follows junctions in Community; the real sim process names (fix `ProcessSimDetector` defaults if they differ from config); real `.pln` format.
- Use the GEN-100 region build.

## Steps

1. Build App on Windows; write `palmlive.json` with the real Community path and `buildRoot`.
2. Remove any manual junction left from GEN-100. In the window, tick the region; confirm `Community\palmfix-<test>` is a junction to the compiled dir (`dir /AL`).
3. Start the sim, fly/slew to T1: blobs gone. While the sim runs, confirm the banner shows.
4. Untick the region, restart the sim: blobs back. Confirm the build output folder is intact (file count before = after).
5. Create a real folder named like another region in Community and confirm the app reports Conflict and leaves it alone.
6. Export a flight plan from the 2024 planner to `tests/fixtures/palmlive/plans/real_export.pln`; run `pick --plan` on it (if LIVE-004 is done).
7. Write `tracking/logs/LIVE-100.md`: versions, results per step, process names found.

## Acceptance criteria

- [ ] One click activates and deactivates; sim loads the linked package.
- [ ] Banner shows while the sim runs.
- [ ] Build output intact after deactivation; conflicts untouched.
- [ ] Real `.pln` fixture committed.

## Verification

Manual on the Windows PC per the steps; evidence in `tracking/logs/LIVE-100.md`. Then on Linux: `dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj`.

## Log

- 2026-11-21 [plan-breakdown] Task created.
