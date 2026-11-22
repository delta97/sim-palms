---
id: LIVE-007
title: "Spawn manager on fake adapter and flight tracks"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-spawn-loop"
depends_on: [LIVE-006]
requires: [none]
agent: simconnect-dotnet-engineer
estimate_h: 5
touches: [palmlive/PalmLive.Core/Spawning/ISimConnectAdapter.cs, palmlive/PalmLive.Core/Spawning/SimEvents.cs, palmlive/PalmLive.Core/Spawning/SpawnOptions.cs, palmlive/PalmLive.Core/Spawning/SpawnManager.cs, palmlive/PalmLive.Core/Spawning/SpawnStats.cs, palmlive/PalmLive.Core/Spawning/ISpawnLedger.cs, palmlive/PalmLive.Tests/Spawning/, palmlive/PalmLive.Tests/Fakes/FakeSimConnectAdapter.cs, tests/fixtures/palmlive/tracks/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`SpawnManager` keeps the nearest palms spawned around the aircraft with altitude-scaled radius, 20% hysteresis, a hard cap and per-tick rate limits, proven by invariant tests on flight tracks with a fake SimConnect adapter. This is the bake-off prototype's brain.

## Context

- Algorithm (9 steps), defaults and invariants: plan section [LIVE spawn loop](../../plans/detailed/04-fs2024-integration.md#live-spawn-loop). Interfaces: [palmlive C# interfaces](../../plans/detailed/04-fs2024-integration.md#palmlive-c-interfaces).
- Defaults are starting values from the source plan (1.5 km at ground, 4 km at 1,000 m AGL, cap 2,000); tuned in LIVE-101.
- `ISpawnLedger` is defined here but only used if passed; LIVE-010 implements it.
- Use `TimeProvider` (`Microsoft.Extensions.Time.Testing.FakeTimeProvider` or a hand-written fake) for timeouts; no real clocks in tests.

## Steps

1. Interfaces and records from the plan (`ISimConnectAdapter`, `SimEvent` family, `SpawnRequest`, `SpawnOptions`, `ISpawnLedger`, `SpawnStats`).
2. `SpawnManager` implementing the 9 steps; internal maps: live (PalmId → ObjectId + record), pending (RequestId → PalmId + time + cancelled flag), failed (PalmId → time).
3. `FakeSimConnectAdapter`: script of aircraft states, create latency in ticks, failure probability with fixed seed, records live object set and every create/remove call.
4. `tests/fixtures/palmlive/tracks/make_tracks.py` (stdlib only) generating `low_pass.csv`, `climb_to_1500m.csv`, `edge_oscillation.csv`, `teleport.csv` around the grid used in tests; commit the CSVs.
5. `TrackReplayer` test helper (CSV → states, one tick per row).
6. Tests: each invariant from the plan; cap respected on a 20,000-palm grid at 1,000 m AGL; teleport removes everything old within the rate-limit bound; failed creates retried after the delay; cancelled pending removed on creation; `Shutdown` → zero live.

## Acceptance criteria

- [ ] All five invariants from the plan hold on all four tracks.
- [ ] No palm spawned twice on `edge_oscillation.csv`.
- [ ] Tests are deterministic (run 3 times, same result).

## Verification

```bash
python3 tests/fixtures/palmlive/tracks/make_tracks.py && git diff --exit-code tests/fixtures/palmlive/tracks/
for i in 1 2 3; do dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj --filter FullyQualifiedName~Spawning || exit 1; done
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
