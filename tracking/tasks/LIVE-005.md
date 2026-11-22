---
id: LIVE-005
title: "App command router, CLI verbs and region window"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-app"
depends_on: [LIVE-003]
requires: [none]
agent: simconnect-dotnet-engineer
estimate_h: 3
touches: [palmlive/PalmLive.Core/Commands/, palmlive/PalmLive.Core/FlightPlans/IFlightPlanRegionPicker.cs, palmlive/PalmLive.Core/FlightPlans/FlightPlanRegionPicker.cs, palmlive/PalmLive.App/Program.cs, palmlive/PalmLive.App/MainForm.cs, palmlive/PalmLive.App/SimConnectFactory.cs, palmlive/PalmLive.Tests/Commands/CommandRouterTests.cs]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`PalmLive.App` gives one-click region switching: a window with a checkbox per region and a sim-running banner, plus CLI verbs for scripting. All verb logic lives in Core and is unit-tested.

## Context

- Verbs, flags, exit codes: plan section [palmlive config and CLI](../../plans/detailed/04-fs2024-integration.md#palmlive-config-and-cli). Window and stub rules: [LIVE app](../../plans/detailed/04-fs2024-integration.md#live-app).
- Stubs created here and filled later: `FlightPlanRegionPicker` (LIVE-004), `SpawnCommand` and `RecordTrackCommand` (LIVE-008), `CleanupCommand` (LIVE-010), `SimConnectFactory` HAS_SIMCONNECT branch (LIVE-008). Each stub returns exit 3 with "not built yet".
- The window can't run on Linux; keep it thin so tests cover the logic through `CommandRouter` and `RegionManager`.

## Steps

1. `Core/Commands/CommandRouter.cs`: `Run(string[] args, TextWriter out, TextWriter err) -> int`, global `--config` and `--build-root`; verbs `regions list|activate|deactivate|only`, `pick`, `spawn`, `record-track`, `cleanup`; `--json` output for `regions list` (array of `{region, version, data_version, state}`); usage text on errors (exit 2).
2. Stub classes `SpawnCommand`, `RecordTrackCommand`, `CleanupCommand` in `Core/Commands/`, `IFlightPlanRegionPicker` + stub `FlightPlanRegionPicker` in `Core/FlightPlans/`.
3. Warning line when the sim is running on activate/deactivate (exit 0).
4. `App/Program.cs`: args → `CommandRouter` (attach to parent console); no args → `MainForm`.
5. `MainForm`: region list (checkbox, region, version, data version, state), toggle calls manager, banner refreshed every 5 s via `ISimProcessDetector`, "Pick from flight plan…" button (shows "not available" if stub), status line; errors shown, never thrown.
6. `App/SimConnectFactory.cs`: `static ISimConnectAdapter? Create()` returning null unless `HAS_SIMCONNECT` (body for that branch: `throw new NotImplementedException()` until LIVE-008).
7. Tests: every verb's exit code with fakes for catalog, linker and detector; JSON output shape; sim-running warning.

## Acceptance criteria

- [ ] All verbs reachable; exit codes as in the plan.
- [ ] `regions list --json` output is valid JSON with the four fields.
- [ ] Window toggles call `RegionManager` (manual check on Windows deferred to LIVE-100).
- [ ] App compiles on Linux (or per LIVE-001 note).

## Verification

```bash
dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj --filter FullyQualifiedName~Commands
dotnet build palmlive/PalmLive.App/PalmLive.App.csproj
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
