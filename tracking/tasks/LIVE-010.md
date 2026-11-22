---
id: LIVE-010
title: "Spawn ledger and crash-safe cleanup"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-cleanup-ledger-and-app-integration"
depends_on: [DEC-007]
requires: [none]
agent: simconnect-dotnet-engineer
estimate_h: 2
touches: [palmlive/PalmLive.Core/Spawning/JsonSpawnLedger.cs, palmlive/PalmLive.Core/Spawning/SpawnManager.cs, palmlive/PalmLive.Core/Commands/CleanupCommand.cs, palmlive/PalmLive.Tests/Spawning/SpawnLedgerTests.cs]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Every spawned object id is persisted, so a crash or forced kill can be cleaned up on the next start (`cleanup` verb), and a clean shutdown always leaves zero objects and an empty ledger.

## Context

- Only if DEC-007 (ADR-0008, informed by the LIVE-009 bake-off) picked live placement; otherwise DEC-007 sets this task to `dropped`.
- Spec: plan section [LIVE cleanup ledger and app integration](../../plans/detailed/04-fs2024-integration.md#live-cleanup-ledger-and-app-integration). Startup behaviour depends on SPIKE-005: whether objects survive a disconnect and whether old ids stay valid in a new connection. Encode both as `SpawnOptions`-style flags read from config, defaulting to SPIKE-005's findings.

## Steps

1. `JsonSpawnLedger(path)`: `Load`, `Save` via temp file + `File.Move(overwrite: true)`; corrupt file → treat as empty and log.
2. `SpawnManager`: save ledger after each tick where the live set changed; `Shutdown` saves an empty ledger after removals complete or timeout (remaining ids stay listed).
3. Startup: `SpawnManager.RecoverFromLedger()` removes listed ids if `idsValidAcrossConnections`; else returns a message "objects from a previous session may remain until the sim restarts".
4. `CleanupCommand`: load ledger, connect, remove, report counts.
5. Tests with the fake adapter: crash simulation (drop manager without Shutdown) → new manager recovers and removes; shutdown timeout leaves remaining ids; corrupt ledger.

## Acceptance criteria

- [ ] Ledger reflects live ids after every changing tick.
- [ ] Recovery path removes leftovers in the fake.
- [ ] Clean shutdown → empty ledger file.

## Verification

```bash
dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj --filter FullyQualifiedName~Spawning
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Depends on DEC-007 instead of LIVE-009: DEC-007 (after the bake-off) decides static vs live and drops this task if static wins. Cross-area reconciliation.
