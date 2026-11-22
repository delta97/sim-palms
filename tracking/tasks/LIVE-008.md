---
id: LIVE-008
title: "SimConnect adapter, spawn and record-track verbs"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-simconnect-adapter"
depends_on: [LIVE-005, LIVE-007, SPIKE-005]
requires: [windows-sim]
agent: simconnect-dotnet-engineer
estimate_h: 4
touches: [palmlive/PalmLive.SimConnect/, palmlive/PalmLive.App/SimConnectFactory.cs, palmlive/PalmLive.Core/Commands/SpawnCommand.cs, palmlive/PalmLive.Core/Commands/RecordTrackCommand.cs, tests/fixtures/palmlive/tracks/recorded_low_pass.csv, tests/fixtures/palmlive/tracks/recorded_approach.csv, tracking/logs/LIVE-008.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

A thin `SimConnectAdapter` implements `ISimConnectAdapter` against the real sim, so `PalmLive.App spawn` runs the spawn loop live (bake-off prototype) and `record-track` records real flight tracks for the xUnit tests.

## Context

- Plan section [LIVE SimConnect adapter](../../plans/detailed/04-fs2024-integration.md#live-simconnect-adapter); SPIKE-005 findings ([SPIKE-005 SimConnect spawn test](../../plans/detailed/04-fs2024-integration.md#spike-005-simconnect-spawn-test)) for DLL paths, on-ground init, latency, message pumping, disconnect behaviour.
- API names from the source plan: `SimConnect_AICreateSimulatedObject_EX1`, `SimConnect_AIRemoveObject`. Use the managed wrapper's equivalents; check names against the 2024 SDK docs, don't guess.
- Keep the adapter thin: no spawn policy logic in it. Only this project references the SDK.
- For smoke tests use the default SimObject title SPIKE-005 used; real palm titles come with ASSET-101.

## Steps

1. `SimConnectAdapter`: `Connect` (named client `PalmLive`), message pump per SPIKE-005, 1 Hz user-aircraft data request for latitude, longitude, altitude above ground (VERIFY SimVar names and units), `RequestCreate` → create call with on-ground init position and a fresh request id, map the assigned-id callback to `ObjectCreatedEvent`, exceptions to `ObjectCreateFailedEvent`, quit/close to `DisconnectedEvent`; `RequestRemove`; thread-safe event queue; `Dispose` closes the connection.
2. Fill `SimConnectFactory` HAS_SIMCONNECT branch.
3. `SpawnCommand` (prototype): open indexes for `--regions` (or all active regions with `index_file`), create `SpawnManager`, 1 Hz loop calling `Tick`, print live count every 10 s, Ctrl+C → `Shutdown(10 s)`.
4. `RecordTrackCommand`: write `t_s,lat,lon,alt_agl_m` at 1 Hz until Ctrl+C.
5. In sim: spawn test with a hand-made index of 50 points at the test block using the default title; confirm objects appear on the ground and disappear when flying away and on Ctrl+C.
6. Record two tracks (low pass over T1, approach) into the fixture files; add them to the LIVE-007 invariant tests (no other test file changes needed if the replayer globs the folder).
7. Write `tracking/logs/LIVE-008.md`: versions, latency seen, issues.

## Acceptance criteria

- [ ] Objects spawn on the ground near the aircraft and are removed beyond radius + 20%.
- [ ] Ctrl+C leaves zero spawned objects (visual check + live count 0).
- [ ] Two recorded tracks committed and passing the invariant tests on Linux.
- [ ] No SDK type leaks outside `PalmLive.SimConnect`.

## Verification

On the Windows PC:
```powershell
dotnet build palmlive/PalmLive.sln -c Release
palmlive\PalmLive.App\bin\Release\net8.0-windows\PalmLive.App.exe spawn --regions <test>
```
On Linux: `dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj --filter FullyQualifiedName~Spawning`.

## Log

- 2026-11-21 [plan-breakdown] Task created.
