---
id: ARCH-008
title: "Write the two example region configs and verify their sources"
status: todo
phase: 1
area: ARCH
kind: build
plan_ref: plans/detailed/01-architecture.md#ws8-example-regions
depends_on: [ARCH-003]
requires: [network]
agent: geo-data-engineer
estimate_h: 2
touches: [regions/san-diego-coastal.yaml, regions/la-westside.yaml, tests/unit/palmcore/test_region_files.py]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
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

- [ ] Both files load with `palmcore.config.load_region` and log no warnings.
- [ ] `id_prefix` values are unique (`sdc`, `law`).
- [ ] The Log lists each verified URL and field name with the date checked, plus any remaining `VERIFY:` items.
- [ ] No data files are added to the repo.

## Verification

```bash
curl -s "https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20?f=pjson" | python -c "import json,sys; d=json.load(sys.stdin); print([f['name'] for f in d['fields']])"
pytest tests/unit/palmcore/test_region_files.py -q
python -c "from pathlib import Path; from palmcore.config import check_regions; print(check_regions(Path('regions')))"   # []
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
