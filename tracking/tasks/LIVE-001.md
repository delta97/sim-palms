---
id: LIVE-001
title: "C# solution skeleton for palmlive"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-solution-skeleton"
depends_on: [DEC-003]
requires: [none]
agent: simconnect-dotnet-engineer
estimate_h: 2
touches: [palmlive/PalmLive.sln, palmlive/global.json, palmlive/Directory.Build.props, palmlive/.gitignore, palmlive/PalmLive.Core/PalmLive.Core.csproj, palmlive/PalmLive.SimConnect/PalmLive.SimConnect.csproj, palmlive/PalmLive.App/PalmLive.App.csproj, palmlive/PalmLive.App/Program.cs, palmlive/PalmLive.Tests/PalmLive.Tests.csproj, palmlive/PalmLive.Tests/SmokeTests.cs]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

The `palmlive/` solution exists with four projects; Core and Tests build and test on Linux, App compiles on Linux, and SimConnect is referenced only when the SDK is present.

## Context

- Spec: plan section [LIVE solution skeleton](../../plans/detailed/04-fs2024-integration.md#live-solution-skeleton).
- DEC-003 must have chosen C#. If it chose Python, don't do this task; rewrite LIVE-001..011 per [LIVE if Python wins DEC-003](../../plans/detailed/04-fs2024-integration.md#live-if-python-wins-dec-003).
- The SDK managed DLL path is VERIFY (SPIKE-005 records it). Keep it in one MSBuild property.
- Pin exact NuGet versions (no floating ranges): xunit, xunit.runner.visualstudio, Microsoft.NET.Test.Sdk, Microsoft.Data.Sqlite.

## Steps

1. `global.json` (SDK 8.0.x, `rollForward: latestFeature`), `Directory.Build.props` with the properties in the plan, `.gitignore` for `bin/` and `obj/`.
2. Create projects with `dotnet new` (classlib, classlib, winforms, xunit), set target frameworks and properties from the plan, add to `PalmLive.sln`.
3. App: conditional `ProjectReference` to SimConnect and `DefineConstants` `HAS_SIMCONNECT` when `HasSimConnectSdk`; `Program.cs` with `[STAThread] Main(string[] args)` returning 0 (verbs come in LIVE-005).
4. Tests csproj: link `../../tests/fixtures/palmlive/**` and `../../palmgen/sql/*.sql` as content (`CopyToOutputDirectory=PreserveNewest`, `LinkBase` `Fixtures` and `Sql`).
5. `SmokeTests.cs`: one test that Core loads, one that the linked fixtures folder exists when present (skip otherwise).
6. If WinForms doesn't compile on Linux with `EnableWindowsTargeting`, record it in the Log and note App compile is Windows-only.

## Acceptance criteria

- [ ] `dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj` passes on Linux.
- [ ] `dotnet build palmlive/PalmLive.App/PalmLive.App.csproj` succeeds on Linux (or the Log explains why not).
- [ ] No SimConnect reference resolved when the SDK is absent.
- [ ] All NuGet versions pinned.

## Verification

```bash
dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj
dotnet build palmlive/PalmLive.App/PalmLive.App.csproj
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
