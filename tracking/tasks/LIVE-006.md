---
id: LIVE-006
title: "SQLite spatial index reader"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-spatial-index-reader"
depends_on: [LIVE-001, GEN-018]
requires: [none]
agent: simconnect-dotnet-engineer
estimate_h: 2
touches: [palmlive/PalmLive.Core/Spatial/, palmlive/PalmLive.Tests/Spatial/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`SqliteSpatialIndex` answers "palms within r metres of here" from a region's `.palms.sqlite`, sorted by distance, fast enough to run every second.

## Context

- Schema and query method: plan sections [Spatial index schema](../../plans/detailed/04-fs2024-integration.md#spatial-index-schema) and [LIVE spatial index reader](../../plans/detailed/04-fs2024-integration.md#live-spatial-index-reader).
- Contract fixture: `tests/fixtures/palmlive/index_small.sqlite` (GEN-018). DDL: `palmgen/sql/palm_index_v1.sql`, linked into the test output by LIVE-001.
- VERIFY: the SQLite native bundle shipped with Microsoft.Data.Sqlite has R-tree enabled; the first test proves it.

## Steps

1. `GeoMath.DistanceM(lat1, lon1, lat2, lon2)` (equirectangular) and `BboxForRadius(lat, lon, r)`.
2. `PalmRecord`, `ISpatialIndex`, `SqliteSpatialIndex(path)` opening read-only; validate `meta.schema_version == "1"`; prepared statement joining `palms_rtree` and `palms`; exact distance filter; sort by (distance, PalmId).
3. Test helper `IndexBuilder` that creates temp indexes from the linked DDL (grid of N palms at spacing s).
4. Tests: R-tree available; contract fixture loads and returns expected palms for a known point; grid query correctness vs brute force (1,000 random queries on a 10,000-palm grid); wrong schema version throws; a 20,000-palm grid query at r = 4 km completes in under 20 ms on average (log the number; don't fail CI on slow machines, use a generous 200 ms ceiling).

## Acceptance criteria

- [ ] Results equal brute force on the random-query test.
- [ ] Contract fixture from GEN-018 reads correctly.
- [ ] Opening a v2 file fails with a clear message.

## Verification

```bash
dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj --filter FullyQualifiedName~Spatial
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
