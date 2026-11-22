---
id: RISK-004
title: Collect airport boundaries and known airport add-ons for default masks
status: todo
phase: 2
area: RISK
kind: research
plan_ref: "plans/detailed/07-risks-and-open-questions.md#mod-and-airport-masks"
depends_on: []
requires: [network]
agent: geo-data-engineer
estimate_h: 3
touches: [docs/compat/airports.md, docs/compat/airports-mask.geojson]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

A GeoJSON of airport boundary polygons for the SoCal target regions, plus a list of known airport add-ons, so region configs can mask airports by default (plan 04 section 7) and avoid clashes with airport scenery (R-13).

## Context

- Target regions (plan 05 Phase 6): San Diego coastal, LA Westside and beaches, rest of the LA basin, other SoCal photogrammetry cities.
- Bbox for San Diego coastal: `[-117.28, 32.70, -117.15, 32.82]`. LA Westside bbox is not fixed yet; use roughly `[-118.55, 33.85, -118.30, 34.10]` and note it as provisional.
- Source suggestion: OSM `aeroway=aerodrome` (and `aeroway=heliport` if large) polygons via Overpass; OSM is ODbL (see RISK-001). FAA airport data is an alternative for points only.
- ARCH-003 decides whether airport masks go into `mask_out` or a separate key (open question in the detailed plan). This file works for either.
- Default buffer suggestion: 200 m around the aerodrome boundary (starting value; REGION tasks can tune).

## Steps

1. Overpass query for `aeroway=aerodrome` ways and relations inside each target bbox (and a SoCal-wide bbox `[-119.0, 32.5, -116.9, 34.5]` for later regions). Save the raw response outside the repo (`data/` is gitignored).
2. Convert to polygons (EPSG:4326). Keep: ICAO or FAA code, name, OSM id.
3. Write `docs/compat/airports-mask.geojson`: FeatureCollection with properties `kind: "airport"`, `icao` (or FAA id), `name`, `osm_id`, `buffer_m: 200`, `source: "OSM"`, `checked`. Store the unbuffered boundary; the buffer is applied by the consumer.
4. Search flightsim.to and payware stores for MSFS 2024 add-ons of the airports found (for example KSAN, KLAX, KSMO, KLGB, KNZY). Record name, URL, airport code.
5. Write `docs/compat/airports.md`: table of airports (code, name, in which target bbox, add-on known yes/no with URL), the buffer rule, and the ODbL attribution note pointing at `docs/licenses/data-sources.md`.

## Acceptance criteria

- [ ] `docs/compat/airports-mask.geojson` parses and contains at least KSAN and KLAX boundaries.
- [ ] Every feature has `kind`, `name`, `buffer_m`, `source`, `checked`.
- [ ] `docs/compat/airports.md` lists every airport in the GeoJSON with a target-region column.
- [ ] Provisional bboxes are labelled as provisional.

## Verification

```bash
python3 - <<'PY'
import json
fc = json.load(open("docs/compat/airports-mask.geojson"))
codes = {f["properties"].get("icao") for f in fc["features"]}
assert {"KSAN","KLAX"} <= codes, codes
for f in fc["features"]:
    assert f["geometry"]["type"] in ("Polygon","MultiPolygon")
    assert f["properties"]["kind"] == "airport" and "buffer_m" in f["properties"]
print(len(fc["features"]), "airports ok")
PY
grep -c "^| K" docs/compat/airports.md   # expect >= 2
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
