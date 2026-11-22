---
id: LIVE-002
title: "Region catalog from palmfix_build.json"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-region-catalog-and-manager"
depends_on: [LIVE-001, GEN-012]
requires: [none]
agent: simconnect-dotnet-engineer
estimate_h: 2
touches: [palmlive/PalmLive.Core/Regions/RegionInfo.cs, palmlive/PalmLive.Core/Regions/IRegionCatalog.cs, palmlive/PalmLive.Core/Regions/RegionCatalog.cs, palmlive/PalmLive.Tests/Regions/RegionCatalogTests.cs, tests/fixtures/palmlive/build_tree/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`RegionCatalog.Load(buildRoot)` lists every built region from its `palmfix_build.json`, giving the region manager names, versions, data dates and the compiled package folder.

## Context

- File format: plan section [Build metadata file](../../plans/detailed/04-fs2024-integration.md#build-metadata-file). Types: [palmlive C# interfaces](../../plans/detailed/04-fs2024-integration.md#palmlive-c-interfaces).
- Contract test: copy `tests/golden/gen-small-static/palmfix_build.json` (written by GEN-012) into the fixture build tree unchanged, so a format change on the Python side breaks this test.

## Steps

1. `RegionInfo` record and `IRegionCatalog`.
2. `RegionCatalog.Load(buildRoot)`: enumerate `*/palmfix_build.json`; System.Text.Json with snake_case naming policy; skip files with `schema_version != 1` or parse errors (collect into `Warnings`); resolve `compiled_package_dir` and `index_file` relative to the project dir; sort by region.
3. Fixture tree `tests/fixtures/palmlive/build_tree/`: `palmfix-fixture-small/palmfix_build.json` (copied from golden, then set `compiled_package_dir` to `out/pkg` and create `out/pkg/.keep`), a second region with `compiled_package_dir: null`, one folder with a broken JSON, one with `schema_version: 2`.
4. Tests for each case.

## Acceptance criteria

- [ ] The golden `palmfix_build.json` parses with all fields.
- [ ] Bad files are skipped with a warning, not an exception.
- [ ] Paths resolve correctly on Linux and use `Path.Combine` (no hard-coded separators).

## Verification

```bash
dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj --filter FullyQualifiedName~RegionCatalog
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
