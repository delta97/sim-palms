---
id: LIVE-012
title: "Build a region from the app (calls palmscan and palmgen)"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-build-a-region-from-the-app"
depends_on: [LIVE-100, SCAN-100, LIVE-011]
requires: [none, windows-sim]
agent: simconnect-dotnet-engineer
estimate_h: 4
touches: [palmlive/PalmLive.Core/Build/, palmlive/PalmLive.Core/Commands/BuildCommand.cs, palmlive/PalmLive.Core/Commands/CommandRouter.cs, palmlive/PalmLive.Core/Config/PalmLiveConfig.cs, palmlive/PalmLive.App/MainForm.cs, palmlive/PalmLive.Tests/Build/, tracking/logs/LIVE-012.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Optional Phase 5 item 2 (`plans/05-phases.md`): from `PalmLive.App`, the user can rebuild a region in one step. A `build` verb and a "Rebuild" button run `palmscan run` and then `palmgen build` for the chosen region, stream their output to a log, and refresh the region list, so a data refresh no longer needs a terminal.

## Context

- Optional. It is not needed by any gate; skip or drop it if the user doesn't want it.
- The app only orchestrates. All logic stays in the Python tools: `python -m palmscan run --region NAME` writes `build/scan/<region>/palms.geojson` and `buildings.geojson` (canonical outputs), then `python -m palmgen build --region NAME` reads them by default and writes `build/palmfix-<region>/` with `palmfix_build.json`, which `RegionCatalog` (LIVE-002) already reads.
- Exit codes to map: palmscan (0 ok, 2 config, 3 schema, 4 source, 5 cache miss) and palmgen (0 ok, 2 input, 3 generation, 4 compile, 5 output check, 6 sim running, 7 tool unavailable); see `plans/detailed/02-detection-pipeline.md#cli` and `plans/detailed/04-fs2024-integration.md#palmgen-cli`. palmgen refuses to build while the sim is running (exit 6) unless SPIKE-004 showed it is safe; the app shows that message and does not pass `--allow-sim-running` by default.
- Depends on LIVE-100 (working region manager and window), SCAN-100 (working `palmscan run`; GEN-100 comes in through LIVE-100) and LIVE-011 only to serialize edits to `MainForm.cs` (LIVE-011 is dropped if DEC-007 picks static, which also satisfies the dependency).
- Process execution goes through an injectable `IProcessRunner`, so Core tests run on Linux with a fake runner. Only the final check needs the Windows PC (`fspackagetool`).
- New config keys in `palmlive.json`: `pythonExe` (default `python`) and `repoRoot` (default: parent of `buildRoot`). Both are optional.

## Steps

1. `Core/Build/IProcessRunner.cs` (`Run(exe, args, workingDir, onLine, cancel) -> int`) and `Core/Build/ProcessRunner.cs` (System.Diagnostics.Process, stdout/stderr line callbacks, kill on cancel).
2. `Core/Build/RegionBuilder.cs`: `BuildAsync(region, BuildRequest{skipScan, models, offline}, IProgress<string>) -> BuildResult{stage, exitCode, logPath}`. Stage 1 `palmscan run --region R [--offline]` unless `skipScan`; stage 2 `palmgen build --region R --models <library|placeholder>`. Stop at the first non-zero exit. Log every line to `<buildRoot>/logs/palmlive-build-<region>-<utc>.log`.
3. `Core/Commands/BuildCommand.cs` and a `build NAME [--skip-scan] [--models library|placeholder] [--offline]` verb in `CommandRouter`. Exit 0 ok, 2 usage/config, 5 a tool failed (message names the stage and the tool's exit code, and for palmgen 6 says "close the sim first").
4. `PalmLiveConfig`: add `pythonExe` and `repoRoot` with defaults; unknown keys still rejected.
5. `MainForm`: a "Rebuild" button for the selected region that runs `RegionBuilder` off the UI thread, shows progress lines, disables region toggles while running, and refreshes the catalog when done.
6. Tests in `PalmLive.Tests/Build/`: fake runner records the two command lines and working dir; `--skip-scan` runs only palmgen; palmscan failure stops before palmgen; palmgen exit 6 gives the sim-running message; log file written; config defaults.
7. On the Windows PC: rebuild the test region from the window with the sim closed; confirm `palmfix_build.json` `built_utc` changes and the region still activates. Record versions and timings in `tracking/logs/LIVE-012.md`.

## Acceptance criteria

- [ ] `PalmLive.App build <region>` runs palmscan then palmgen and returns 0 on success.
- [ ] A failing stage stops the build and the message names the stage and exit code.
- [ ] palmgen's sim-running refusal is shown as "close the sim first", not as a crash.
- [ ] Core tests pass on Linux with the fake runner.
- [ ] Manual Windows check recorded in `tracking/logs/LIVE-012.md`.

## Verification

```bash
dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj --filter "FullyQualifiedName~Build"
```
Manual on the Windows PC: `PalmLive.App.exe build <test-region>; echo $LASTEXITCODE` → 0, then `regions list --json` shows the new `version`/`data_version`.

## Log

- 2026-11-22 [reconcile] Task created via `tasks.py new` and filled in: the optional "build a region from the app" item (plans/05 Phase 5 item 2) was untasked in plan 04 (question 7). Depends on LIVE-100, SCAN-100, LIVE-011 (MainForm.cs ordering).
