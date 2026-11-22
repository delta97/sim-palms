---
id: RISK-001
title: Audit data source licenses and terms (inventories, OSM, footprints, LiDAR)
status: todo
phase: 1
area: RISK
kind: research
plan_ref: "plans/detailed/07-risks-and-open-questions.md#license-audit"
depends_on: []
requires: [network]
agent: scribe
estimate_h: 4
touches: [docs/licenses/data-sources.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

One file records, for every data source the pipeline may use, the license or terms, the exact clauses on redistribution, derived works and attribution, the date checked, and open questions for the user. DEC-009, DEC-001 and DEC-010 decide from this file.

## Context

- Risks: R-14 (licensing if published), R-15 (source disappears).
- Sources in `plans/02-detection-pipeline.md` section 1 and `plans/README.md` Sources.
- Do not state legal conclusions ("this is allowed"). Quote the terms, summarise them neutrally, and list questions for the user.
- Personal use is the default (DEC-001). This audit matters most if the user publishes, but DEC-009 also uses it in Phase 1.

## Steps

1. For each source below, find the authoritative terms page and record the fields in step 2:
   - LA County street tree compilation `https://github.com/stiles/la-trees` (check the repo LICENSE, README, and whether data terms differ from code terms; records came via public records requests).
   - StreetsLA tree inventory `https://streets.lacity.gov/resources/tree-inventory` and the LA GeoHub copy, if any.
   - City of San Diego street trees (ArcGIS layer `https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20`; also the City open data portal terms and the layer's disclaimer text).
   - OpenStreetMap (ODbL 1.0; OSMF attribution guidelines; note what "produced work" and "derivative database" mean in the license text, quoted).
   - Microsoft Global ML Building Footprints (GitHub repo license file).
   - USGS 3DEP LiDAR (`https://registry.opendata.aws/usgs-lidar/` and USGS data policy).
   - Any county or city building outline datasets raised by DEC-009 (LA County / LARIAC, SanGIS): terms only, if quickly found.
2. Per source, record: name | URL of terms | license name/version | redistribution clause (quoted) | attribution requirement (quoted) | share-alike or derived-data clause (quoted) | accuracy disclaimer | date checked | alternate download location (R-15) | questions for the user.
3. Write `docs/licenses/data-sources.md`: intro (purpose, "not legal advice; terms quoted as of the date checked"), one section per source, then a summary table with columns Source | License | Attribution needed | Redistribution terms clear? (yes / unclear / restrictive) | Questions.
4. Add a "Questions for the user" list at the end, numbered, each linked to its source section.

## Acceptance criteria

- [ ] All six core sources (LA compilation, StreetsLA, San Diego, OSM, Microsoft footprints, USGS 3DEP) have a section with a terms URL and a date checked.
- [ ] Each section quotes the redistribution and attribution text, or states "no terms found" with the pages searched.
- [ ] The summary table has one row per source.
- [ ] No sentence states that something is legally permitted or forbidden; open points are phrased as questions.

## Verification

```bash
test -f docs/licenses/data-sources.md && echo ok
for s in "la-trees" "StreetsLA" "San Diego" "ODbL" "Microsoft" "3DEP"; do grep -q "$s" docs/licenses/data-sources.md && echo "found $s" || echo "MISSING $s"; done
grep -c "Date checked\|date checked" docs/licenses/data-sources.md   # expect >= 6
grep -n "Questions for the user" docs/licenses/data-sources.md
```

Read the file once and confirm no legal conclusions are stated.

## Log

- 2026-11-21 [plan-breakdown] Task created.
