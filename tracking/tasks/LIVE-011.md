---
id: LIVE-011
title: "Live palms in the app (LiveSession)"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-cleanup-ledger-and-app-integration"
depends_on: [LIVE-010]
requires: [none]
agent: simconnect-dotnet-engineer
estimate_h: 3
touches: [palmlive/PalmLive.Core/Spawning/LiveSession.cs, palmlive/PalmLive.Core/Commands/SpawnCommand.cs, palmlive/PalmLive.App/MainForm.cs, palmlive/PalmLive.Tests/Spawning/LiveSessionTests.cs]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

The PalmLive window has a "Live palms" toggle that runs the spawner for all active regions with an index, shows the live count, and shuts down cleanly; the `spawn` verb uses the same `LiveSession`.

## Context

- Only if DEC-007 (ADR-0008) picked live placement; otherwise DEC-007 sets it to `dropped`.
- Plan section [LIVE cleanup ledger and app integration](../../plans/detailed/04-fs2024-integration.md#live-cleanup-ledger-and-app-integration).
- Spawn options come from `palmlive.json` `spawn` (LIVE-003 config).

## Steps

1. `LiveSession(RegionManager, Func<ISimConnectAdapter?>, PalmLiveConfig, ISpawnLedger, TimeProvider)`: `Start()` opens `SqliteSpatialIndex` for active regions with `IndexFile` (skip others with a message), runs recovery, starts a 1 Hz timer calling `Tick`; `Stop()` → `Shutdown`; `Status` (connected, live, pending, regions).
2. Reconnect: on `DisconnectedEvent`, retry `Connect` every 10 s while started.
3. `SpawnCommand` refactored to use `LiveSession`.
4. `MainForm`: toggle (disabled with tooltip when `SimConnectFactory.Create()` returns null), live count label refreshed each second, Stop on window close.
5. Tests with the fake adapter and temp indexes: start with two active regions; region without index skipped; stop → zero live; disconnect → reconnect resumes.

## Acceptance criteria

- [ ] LiveSession tests pass on Linux.
- [ ] Closing the window stops the session (code path covered by `Stop` test).
- [ ] `spawn` verb and window share one code path.

## Verification

```bash
dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj --filter FullyQualifiedName~LiveSession
dotnet build palmlive/PalmLive.App/PalmLive.App.csproj
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Live-only condition now refers to DEC-007/ADR-0008 (the decision task), not LIVE-009 (the measurement). Cross-area reconciliation.
