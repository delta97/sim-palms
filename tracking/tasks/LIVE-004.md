---
id: LIVE-004
title: "Flight plan region picker (optional)"
status: todo
phase: 5
area: LIVE
kind: build
plan_ref: "plans/detailed/04-fs2024-integration.md#live-flight-plan-pick"
depends_on: [LIVE-005]
requires: [none]
agent: simconnect-dotnet-engineer
estimate_h: 2
touches: [palmlive/PalmLive.Core/FlightPlans/PlnParser.cs, palmlive/PalmLive.Core/FlightPlans/FlightPlanRegionPicker.cs, palmlive/PalmLive.Tests/FlightPlans/, tests/fixtures/palmlive/plans/dms_ksan_klax.pln, tests/fixtures/palmlive/plans/decimal_short.pln]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`pick --plan route.pln` (and the window button) selects the regions a flight passes near and can activate exactly those.

## Context

- Spec: plan section [LIVE flight plan pick](../../plans/detailed/04-fs2024-integration.md#live-flight-plan-pick). Optional per the source plan; skip if time is short.
- VERIFY: the 2024 `.pln` format. Parse tolerantly; LIVE-100 adds a real exported plan as a fixture. If that fixture fails, fix the parser then.
- Replace the stub `FlightPlanRegionPicker` created in LIVE-005; keep its interface.

## Steps

1. `PlnParser.Parse(path) -> IReadOnlyList<(double Lat, double Lon)>`: XML, find all `WorldPosition` elements under waypoint elements (match local names, ignore namespaces); parse DMS `N32° 44' 2.20",W117° 11' 22.80",+000017.00` and decimal `32.73,-117.19[,alt]`; error with line info on bad input.
2. `FlightPlanRegionPicker.Pick(plnPath, regions, corridorKm)`: local equirectangular metres around the route midpoint; region picked if its bbox comes within `corridorKm` of any route segment or contains the last waypoint; result sorted by region.
3. Fixtures: `tests/fixtures/palmlive/plans/dms_ksan_klax.pln`, `decimal_short.pln` (hand-written, clearly marked synthetic in an XML comment).
4. Tests: both formats parse; region on route picked, region 50 km away not; destination-only region picked; malformed file error.

## Acceptance criteria

- [ ] Both fixture formats parse to the expected coordinates (±1e-6°).
- [ ] Corridor and destination rules tested.
- [ ] `pick --plan <fixture> --apply` works through `CommandRouter` in a test.

## Verification

```bash
dotnet test palmlive/PalmLive.Tests/PalmLive.Tests.csproj --filter FullyQualifiedName~FlightPlans
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
