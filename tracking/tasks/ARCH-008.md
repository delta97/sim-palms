---
id: ARCH-008
title: "Write the two example region configs and verify their sources"
status: review
phase: 1
area: ARCH
kind: build
plan_ref: plans/detailed/01-architecture.md#ws8-example-regions
depends_on: [ARCH-003]
requires: [network]
agent: geo-data-engineer
estimate_h: 2
touches: [regions/san-diego-coastal.yaml, regions/la-westside.yaml, tests/unit/palmcore/test_region_files.py]
owner: claude-agent
branch: task/arch-008-write-the-two-example-region-configs-and
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ARCH-008"
updated: 2026-11-22
---

## Goal

`regions/san-diego-coastal.yaml` and `regions/la-westside.yaml`, valid against the region schema, with inventory URLs and field names checked against the live endpoints. SCAN's Phase 1 work then has real configs to run against.

## Context

- The full San Diego YAML and the LA Westside spec are in the plan_ref section WS8. Key rules are in `plans/detailed/01-architecture.md#ws7-region-config`. Inventory entries use `name` (not `id`); masks use `masks.airports`.
- Network is needed only for endpoint metadata (field lists, file location). Don't download whole datasets, and don't commit any downloaded data.
- `VERIFY:` (Q17) for San Diego: the layer's id field (expected `OBJECTID`) and that `SPECIES_NAME` exists. For LA: the compilation's file URL, species field and id field in github.com/stiles/la-trees.
- SCAN-specific field keys (`common_name_field`, `status_field`, `height_field`, `date_field`) are optional. Fill them only if the field list shows an obvious match, and note each one in the Log.
- The priors are the source plan's placeholders; SCAN replaces them (`palmscan priors`). The LA Westside bbox is a starting value, which REGION tasks may tune.
- The unit test is offline. It loads the files; it never fetches the URLs.

## Steps

1. Fetch `https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20?f=pjson`. Record in the Log: the layer name, the field names, the object-id field, whether `SPECIES_NAME` exists, and any status/height/date fields.
2. Write `regions/san-diego-coastal.yaml` as in WS8, with the confirmed `id_field`.
3. Read the `stiles/la-trees` README and file list. Find the GeoJSON or CSV compilation and its field names. Prefer GeoJSON. For CSV, set `format: csv` with `lon_field`/`lat_field`. If the file is too large for a raw URL, set `path: data/manual/la-trees/<file>` and write the download steps in a YAML comment.
4. Write `regions/la-westside.yaml` (`id_prefix: law`, other values per WS8) with the confirmed fields.
5. Check whether StreetsLA has a machine-readable endpoint. If yes, add it as a second inventory source `streetsla_trees`. If not, add a comment for SCAN.
6. Any value you could not confirm keeps a `# VERIFY:` comment on its line, and the Log says why.
7. Write `tests/unit/palmcore/test_region_files.py`: every `regions/*.yaml` loads with `load_region`; `check_regions(<repo>/regions)` returns `[]`; each region's bbox lies within the sanity envelope `[-125, 24, -66, 50]`.
8. Run the Verification commands.

## Acceptance criteria

- [x] Both files load with `palmcore.config.load_region` and log no warnings.
- [x] `id_prefix` values are unique (`sdc`, `law`).
- [x] The Log lists each verified URL and field name with the date checked, plus any remaining `VERIFY:` items.
- [x] No data files are added to the repo.

## Verification

```bash
curl -s "https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20?f=pjson" | python -c "import json,sys; d=json.load(sys.stdin); print([f['name'] for f in d['fields']])"
pytest tests/unit/palmcore/test_region_files.py -q
python -c "from pathlib import Path; from palmcore.config import check_regions; print(check_regions(Path('regions')))"   # []
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/arch-008-write-the-two-example-region-configs-and worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ARCH-008
- 2026-11-22 [claude-agent] Checked 2026-11-22: SD layer https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20?f=pjson -> name 'Trees (Street Trees)', esriGeometryPoint, maxRecordCount 2000, formats JSON/geoJSON/PBF. Object-id field OBJECTID (esriFieldTypeOID). SPECIES_NAME exists (String, e.g. 'Washingtonia robusta'); query SPECIES_NAME LIKE '%Washingtonia%' returned count 14561. Other fields: COMMON_NAME, HEIGHT_FT (ft), DBH_IN, INSPCTDATE (Date), CONDITION (health rating, not status), MAPNG_STAT_CD (unclear). Q17 resolved: id_field OBJECTID confirmed, SPECIES_NAME confirmed.
- 2026-11-22 [claude-agent] SD config SCAN keys filled: common_name_field COMMON_NAME, height_field HEIGHT_FT (+height_units ft), dbh_field DBH_IN, date_field INSPCTDATE (inspection date, not planting). status_field left unset: CONDITION is a health rating and MAPNG_STAT_CD's meaning is unconfirmed.
- 2026-11-22 [claude-agent] Checked 2026-11-22: LA compilation. Repo github.com/stiles/la-trees has per-city files plus S3 mirrors. County-wide GeoJSON https://s3.us-west-1.amazonaws.com/stilesdata.com/jacarandas/la_county_tree_locations.geojson (HTTP 200, 626,629,879 bytes; properties id, place, species, ispalm, mexfanpalm, ...; species values are common names e.g. 'Mexican Fan Palm', 'Queen Palm'). Too large for a raw URL, so la-westside uses path data/manual/la-trees/la_county_tree_locations.geojson with download steps in a YAML comment. species_field species, id_field id. LA city only file https://stilesdata.com/trees/los-angeles/la_street_trees_latlon.geojson (165,657,142 bytes; properties site_id, tree_common) not used: it lacks Santa Monica and Culver City.
- 2026-11-22 [claude-agent] VERIFY: la-westside id_field 'id' is a row index of the compilation, stability across releases unknown; kept with a VERIFY comment. Species are common names only, SCAN must normalise. Only the first ~1.8 kB and a 1.5 MB mid-file slice were read, not the whole file.
- 2026-11-22 [claude-agent] StreetsLA (step 5): only a GeoServer WFS, https://geola.daveytreekeeper.com/geoserver/Treekeeper/ows, typeName Treekeeper:streetsla_UFDSpeciesLabel (GetCapabilities OK; GetFeature count=1 returned site_id, tree_common, EPSG:2229, 925,735 features). Inventory type enum has no WFS, so no streetsla_trees source; comment for SCAN added in la-westside.yaml.
- 2026-11-22 [claude-agent] Other endpoints checked 2026-11-22: 3DEP EPT on S3 bucket usgs-lidar-public: .../USGS_LPC_CA_SanDiegoQL1_2014_LAS_2016/ept.json and .../USGS_LPC_CA_LosAngeles_2016_LAS_2018/ept.json both HTTP 200 (https://s3-us-west-2.amazonaws.com/usgs-lidar-public/ept.json root 404, expected). Overpass https://overpass-api.de/api/interpreter: needs a User-Agent (406 without); a tiny bbox count query returned 31 tree nodes in 32.75,-117.20,32.76,-117.19; larger Washingtonia query got 502 at-capacity (transient). Nothing downloaded or committed.
- 2026-11-22 [claude-agent] Verification: pytest 262 passed; ruff check and format clean; mypy clean; check_regions(regions) -> [].
- 2026-11-22 [claude-agent] Status in_progress -> review.
