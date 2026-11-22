---
id: RISK-004
title: Collect airport boundaries and known airport add-ons for default masks
status: review
phase: 2
area: RISK
kind: research
plan_ref: "plans/detailed/07-risks-and-open-questions.md#mod-and-airport-masks"
depends_on: []
requires: [network]
agent: geo-data-engineer
estimate_h: 3
touches: [docs/compat/airports.md, docs/compat/airports-mask.geojson]
owner: claude-agent
branch: task/risk-004-collect-airport-boundaries-and-known-air
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/RISK-004"
updated: 2026-11-22
---

## Goal

A GeoJSON of airport boundary polygons for the SoCal target regions, plus a list of known airport add-ons, so region configs can mask airports by default (plan 04 section 7) and avoid clashes with airport scenery (R-13).

## Context

- Target regions (plan 05 Phase 6): San Diego coastal, LA Westside and beaches, rest of the LA basin, other SoCal photogrammetry cities.
- Bbox for San Diego coastal: `[-117.28, 32.70, -117.15, 32.82]`. LA Westside bbox is not fixed yet; use roughly `[-118.55, 33.85, -118.30, 34.10]` and note it as provisional.
- Source suggestion: OSM `aeroway=aerodrome` (and `aeroway=heliport` if large) polygons via Overpass; OSM is ODbL (see RISK-001). FAA airport data is an alternative for points only.
- Decided (ARCH-003, 2026-11-22): region configs read airport masks from `masks.airports.{enabled, buffer_m, path}`, and `path` defaults to this task's `docs/compat/airports-mask.geojson`, so every region masks airports by default (plan 04 section 7). Manual extras are `mask_out` entries with `kind: airport`. GEN-016 (first real build) depends on this file existing.
- Buffer: palmgen applies `masks.airports.buffer_m` (ARCH-003 default 100 m). The per-feature `buffer_m` property records the suggested value (start at 100 m); REGION tasks tune the config key, not the file.

## Steps

1. Overpass query for `aeroway=aerodrome` ways and relations inside each target bbox (and a SoCal-wide bbox `[-119.0, 32.5, -116.9, 34.5]` for later regions). Save the raw response outside the repo (`data/` is gitignored).
2. Convert to polygons (EPSG:4326). Keep: ICAO or FAA code, name, OSM id.
3. Write `docs/compat/airports-mask.geojson`: FeatureCollection with properties `kind: "airport"`, `icao` (or FAA id), `name`, `osm_id`, `buffer_m: 100` (suggestion; see Context), `source: "OSM"`, `checked`. Store the unbuffered boundary; the buffer is applied by the consumer.
4. Search flightsim.to and payware stores for MSFS 2024 add-ons of the airports found (for example KSAN, KLAX, KSMO, KLGB, KNZY). Record name, URL, airport code.
5. Write `docs/compat/airports.md`: table of airports (code, name, in which target bbox, add-on known yes/no with URL), the buffer rule, and the ODbL attribution note pointing at `docs/licenses/data-sources.md`.

## Acceptance criteria

- [x] `docs/compat/airports-mask.geojson` parses and contains at least KSAN and KLAX boundaries. (60 features; KSAN and KLAX present, Polygon/MultiPolygon only)
- [x] Every feature has `kind`, `name`, `buffer_m`, `source`, `checked`. (Checked in Python: no missing props)
- [x] `docs/compat/airports.md` lists every airport in the GeoJSON with a target-region column. (60 table rows, target region column present)
- [x] Provisional bboxes are labelled as provisional. (LA Westside labelled PROVISIONAL in airports.md and GeoJSON metadata)

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
- 2026-11-22 [reconcile] ARCH-003 decided the key: this file is the default airport mask (masks.airports.path defaults to docs/compat/airports-mask.geojson; manual extras are mask_out entries with kind: airport). Buffer applied by palmgen from masks.airports.buffer_m (ARCH-003 default 100 m); the per-feature buffer_m is now a suggestion aligned to 100 m. GEN-016 depends on this task. Cross-area reconciliation.
- 2026-11-22 [claude-agent] Claimed. branch=task/risk-004-collect-airport-boundaries-and-known-air worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/RISK-004
- 2026-11-22 [claude-agent] Overpass pulls 2026-11-22 (UA sim-palms-research/0.1; default curl UA got 406): San Diego bbox 9 elements, LA Westside 3, SoCal-wide bigger set; raw in data/raw/overpass (gitignored). Converted with scratchpad script: 69 aerodrome/heliport features, 9 with no ICAO/FAA/ref/iata code dropped, 60 kept.
- 2026-11-22 [claude-agent] Verification (task block, python -): 60 airports ok; KSAN and KLAX present; grep -c '^| K' airports.md = 39 (>=2). Required props present on all 60. Add-on searches (WebSearch, 2026-11-22) for KSAN, KLAX, KSMO, KLGB, KNZY; URLs recorded in airports.md; other airports marked not searched.
- 2026-11-22 [claude-agent] Gaps: docs/licenses/data-sources.md does not exist in this worktree, so the ODbL link is a VERIFY. Add-on prices and MSFS 2024 compatibility are from search snippets only (VERIFY). Region is by polygon-centre bbox, so KNZY sits on the San Diego bbox edge (VERIFY).
- 2026-11-22 [claude-agent] Status in_progress -> review.
