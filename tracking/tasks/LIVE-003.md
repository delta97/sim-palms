---
id: LIVE-003
title: "Folder linker, region manager, sim detector and config"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-region-catalog-and-manager"
depends_on: [LIVE-002]
requires: [none]
agent: simconnect-dotnet-engineer
estimate_h: 3
touches: [palmlive/PalmLive.Core/Regions/IFolderLinker.cs, palmlive/PalmLive.Core/Regions/FolderLinker.cs, palmlive/PalmLive.Core/Regions/RegionManager.cs, palmlive/PalmLive.Core/Regions/RegionConflictException.cs, palmlive/PalmLive.Core/Sim/ISimProcessDetector.cs, palmlive/PalmLive.Core/Sim/ProcessSimDetector.cs, palmlive/PalmLive.Core/Config/PalmLiveConfig.cs, palmlive/PalmLive.Tests/Regions/RegionManagerTests.cs, palmlive/PalmLive.Tests/Regions/FolderLinkerTests.cs, palmlive/PalmLive.Tests/Config/PalmLiveConfigTests.cs]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Regions activate and deactivate by creating and removing a folder link `Community/<package_name>` → compiled package, with a state model that never touches a real folder or someone else's link. Config loads from `palmlive.json`; a detector reports whether the sim is running.

## Context

- State table, safety rules, linker behaviour: plan section [LIVE region catalog and manager](../../plans/detailed/04-fs2024-integration.md#live-region-catalog-and-manager). Config: [palmlive config and CLI](../../plans/detailed/04-fs2024-integration.md#palmlive-config-and-cli).
- Linux tests use real symlinks in temp dirs. Junction behaviour on NTFS and whether MSFS 2024 follows junctions are checked in LIVE-100.
- Safety first: deleting through a link must never delete the build output. A test must prove it.

## Steps

1. `PalmLiveConfig` record + `Load(path)` (case-insensitive JSON, validation listing all problems; `linkType` in {junction, symlink}; `communityPath` and `buildRoot` must exist).
2. `IFolderLinker` and `FolderLinker(linkType)`: junction via `cmd.exe /c mklink /J` on Windows (check exit code and that the link exists afterwards), symlink via `Directory.CreateSymbolicLink`; `IsLink`/`GetLinkTarget` via `FileSystemInfo.LinkTarget`; `RemoveLink` refuses non-links.
3. `RegionManager` with `List`, `Activate`, `Deactivate`, `ActivateOnly` implementing the state table; compare targets with full normalised paths (case-insensitive on Windows).
4. `ProcessSimDetector(names)`.
5. Tests: each state from the table; activate idempotent; broken link repaired; conflict and foreign link untouched (directory listing before = after); `RemoveLink` leaves the target folder and a file inside it intact; `ActivateOnly` result; config validation errors.

## Acceptance criteria

- [ ] Every row of the state table has a test.
- [ ] Safety test proves target contents survive deactivation.
- [ ] No recursive delete anywhere in Core (`grep -rn "recursive: true" palmlive/PalmLive.Core` empty).

## Verification

```bash
dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj --filter "FullyQualifiedName~Regions|FullyQualifiedName~Config"
grep -rn "recursive: true" palmlive/PalmLive.Core   # expect no output
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
