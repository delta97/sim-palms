---
id: RISK-003
title: Inventory other palm and tree mods and their coverage for mask_out defaults
status: todo
phase: 1
area: RISK
kind: research
plan_ref: "plans/detailed/07-risks-and-open-questions.md#mod-and-airport-masks"
depends_on: []
requires: [network, human]
agent: geo-data-engineer
estimate_h: 3
touches: [docs/compat/other-mods.md, docs/compat/mods-coverage.geojson]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

A list of known SoCal palm and tree mods (with which ones the user runs) and a GeoJSON of their approximate coverage areas, ready for REGION tasks to copy into each region's `mask_out`. This prevents duplicate palms (R-13).

## Context

- `plans/04-fs2024-integration.md` section 7: add other mods' coverage to `mask_out`; overlapping exclusions are harmless, duplicate palms are not.
- `mask_out` format is defined by ARCH-003 (region config schema). This task writes candidate polygons only, not region config.
- Known examples: LA palm enhancement mod `https://flightsim.to/addon/81258/los-angeles-palm-enhancement`; Bijan's Seasons 2024 Enhanced (global vegetation; check whether it places palms in SoCal).
- Coverage is often described only in text or screenshots. Approximate polygons are fine; mark confidence.

## Steps

1. Ask the user for the list of folders in their Community folder (names only), or a screenshot of it. Note which are tree/vegetation/city mods.
2. Search flightsim.to and the MSFS forums for MSFS 2024 (and 2020 mods that still load in 2024) palm, tree or vegetation mods covering Los Angeles, San Diego and other SoCal photogrammetry cities. Record: name, author, URL, version/date, what it changes (adds palms / replaces trees / exclusions), coverage as described, user runs it (yes/no/unknown).
3. Write `docs/compat/other-mods.md` with one row per mod and a short "how to use" note: REGION tasks copy polygons for mods the user runs into `mask_out`; others are listed for publishing (DEC-001).
4. Write `docs/compat/mods-coverage.geojson`: a FeatureCollection, EPSG:4326, one Polygon or MultiPolygon per mod, properties `kind: "mod"`, `name`, `url`, `confidence` (`high` = author-published area, `medium` = from screenshots/description, `low` = guess), `user_runs` (true/false/null), `checked` (date).
5. Validate the GeoJSON parses and every polygon is valid (shapely `is_valid` if available, or `python3 -c "import json; json.load(open(...))"` at minimum).

## Acceptance criteria

- [ ] `docs/compat/other-mods.md` lists every mod found, with URL and `user_runs`.
- [ ] The user's Community folder list was requested; the answer (or "not answered") is noted.
- [ ] `docs/compat/mods-coverage.geojson` parses as GeoJSON and has one feature per mod that has a known area.
- [ ] Every feature has `kind`, `name`, `confidence` and `checked`.

## Verification

```bash
python3 - <<'PY'
import json
fc = json.load(open("docs/compat/mods-coverage.geojson"))
assert fc["type"] == "FeatureCollection"
for f in fc["features"]:
    p = f["properties"]
    assert p["kind"] == "mod" and p["name"] and p["confidence"] in ("high","medium","low"), p
print(len(fc["features"]), "features ok")
PY
grep -c "flightsim.to" docs/compat/other-mods.md   # expect >= 1
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [integrator] integrator: on the sim PC (2026-11-22) the Community folder (%APPDATA%\Microsoft Flight Simulator 2024\Packages\Community) holds one add-on, atmospheremod-weather (weather); no palm or tree mods installed. Still need the user's list of mods they plan to use.
