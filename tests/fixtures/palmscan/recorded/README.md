# Recorded live source fixtures (SCAN-007)

Real responses from the Phase 1 sources, recorded on **2026-11-22** with the merged adapters
(`palmscan.http.HttpClient`, generic User-Agent `palmscan/<version>`, a handful of requests, no loops)
and then trimmed to a few dozen features and the fields the adapters use. Raw downloads stayed in the
gitignored `data/`. `tests/unit/palmscan/test_scan_recorded_sources.py` replays every file offline.
Re-record when a source changes format.

Recording bboxes are 400 m x 400 m (lon_min, lat_min, lon_max, lat_max):

| Name | Centre | Bbox |
|---|---|---|
| San Diego | -117.2531, 32.7893 (Mission Beach, from the plan) | -117.25523713722649, 32.78750337765001, -117.25096286277352, 32.79109662234998 |
| OSM palms | -117.2094, 32.7812 (the San Diego OSM trees that carry a species tag are almost all here) | -117.21153694263549, 32.77940337765001, -117.20726305736451, 32.782996622349984 |
| Santa Monica | -118.4975, 34.0132 (Ocean Av / Palisades Park palms) | -118.49966745499573, 34.01140337765001, -118.49533254500427, 34.01499662234998 |

## Files

### `sd_street_trees/` - City of San Diego layer 20 (ArcGIS REST)

- URL: `https://webmaps.sandiego.gov/arcgis/rest/services/DSD/Environment/MapServer/20` (layer "Trees (Street Trees)", ArcGIS Server 11.5).
- `layer_info.json`: `?f=json`, trimmed (keys the adapter ignores dropped; `maxRecordCount`, `advancedQueryCapabilities`, field list and coded domains are verbatim).
- `query_page_0.json`: the adapter's real `/query` response for the San Diego bbox (220 features, 209 inside the bbox), reduced to 49 features and 10 attributes (`OBJECTID, COMMON_NAME, SPECIES_NAME, MAPNG_STAT_CD, CONDITION, HEIGHT_FT, DBH_IN, INSPCTDATE, last_edited_date, INST_YR`). User-name and address fields are dropped. 40 standing (`AB`) and 9 removed (`RM`) rows, chosen to cover every species seen.
- License: no explicit grant (RISK-001, `docs/licenses/data-sources.md` section 3); the layer's `licenseInfo` is an as-is disclaimer and `copyrightText` credits the City of San Diego Transportation Department. Only this minimal sample is committed.

### `la_trees/` - stiles/la-trees compilation

- `la_county_sample.geojson`: 14 verbatim rows of the file the region config uses, `https://s3.us-west-1.amazonaws.com/stilesdata.com/jacarandas/la_county_tree_locations.geojson` (626,629,879 bytes, `Last-Modified: Fri, 31 May 2024 15:28:42 GMT`, ETag `02cd70f5a918a7325175367fbc10d480-37`). The file was **not** downloaded: 2 MB to 4 MB HTTP Range reads at ten offsets (head, 150 MB, 310 MB, 400 to 620 MB, tail) gave 32,244 distinct rows; these 14 are the ones inside the Santa Monica bbox. Original header kept. Because the rows are a sample, this is not every tree in the bbox.
- `santa_monica_clip.geojson`: 42 verbatim rows of a real 400 m clip (332 trees) of the per-city file `https://raw.githubusercontent.com/stiles/la-trees/main/data/municipalities/santa-monica/santa-monica.geojson` (25,673,644 bytes, downloaded to `data/` only). Original header kept, including `crs` EPSG:2229. Rows chosen to cover every species in the clip. Attributes are verbatim.
- License: the repository root has an MIT `LICENSE` (data coverage unclear), and the README says records come from municipalities through public-records requests or open-data portals (`docs/licenses/data-sources.md` section 1). Only small samples are committed.

### `osm_trees/` - OSM `natural=tree` via Overpass

- `trees_response.json`: the adapter's query (`OSM_TREES_QUERY`) against `https://overpass-api.de/api/interpreter` for the OSM palms bbox (OSM base timestamp 2026-11-22T19:59Z); 54 nodes reduced to 36 (30 with a species-like tag, 6 without). Tag values are verbatim.
- `empty_response.json`: the same query for the San Diego bbox: zero tree nodes, so OSM adds nothing there.
- License: OpenStreetMap data, ODbL 1.0, (c) OpenStreetMap contributors (https://www.openstreetmap.org/copyright). Records carry `extra["license"]` and `extra["attribution"]`.

### `osm_buildings/` - OSM buildings via Overpass

- `buildings_response.json`: `BUILDINGS_QUERY` for the San Diego bbox (233 ways, 247 KB), reduced to the 32 closest to the centre. No multipolygon relations occurred in this bbox, so the relation path is covered only by the synthetic fixture in `tests/fixtures/palmscan/buildings/`. ODbL as above.

## Answers to the open source-field questions (SCAN-007)

### San Diego layer 20 (`sd_street_trees`)

| Item | Answer (evidence: layer JSON and queries, 2026-11-22) |
|---|---|
| `SPECIES_NAME` exists | Yes. `esriFieldTypeString`, length 50, alias "Biological Species". Layout: Latin binomial, e.g. `Washingtonia robusta`; genus-only rows end in `spp.` (`Palm spp.`, `Sabal spp.`, `Chamaedorea spp.`); a hybrid is `Washingtonia x filibusta`; cultivars are quoted (`Juniperus chinensis 'Torulosa'`). It is **null** on rows never inspected: 100,874 of 275,614 `AB` rows citywide (37%) and on all removed rows. Those rows only have `COMMON_NAME` (never null on `AB`), so `common_name_field` is required, and `normalize_species(raw, common)` already falls back to it. Both fields are truncated at their length (`Fishtail Palm; Mountain Fishta`). |
| Status field | **`MAPNG_STAT_CD`** (string, 2): coded domain `AB` AS BUILT, `AN` ABANDONED, `OP` OPERATIONAL, `RM` REMOVED, `NM` NOT MAPPED. Only `AB` (275,614) and `RM` (90,042 = 25%) occur citywide. JSON returns the code, not the label. The region file had no `status_field`, so removed palms (36 of 47 `RM` rows in the recording bbox are "Mexican Fan Palm") would have been ingested as palms. Fixed: `status_field: MAPNG_STAT_CD` in `regions/san-diego-coastal.yaml` and a whole-string status code `rm` in `non_tree_markers.yaml`. `CONDITION` is health: coded domain `GOOD/FAIR/POOR/DEAD`, and removed rows show `2` or null. |
| Date field | `INSPCTDATE` (`esriFieldTypeDate`, epoch ms): inspection date, set only on inspected rows; citywide 2021-09-13 to 2026-03-31, all 2022 in the recording bbox. Other dates: `INST_YR` (date; many rows are 2001, so it looks like a default, not a planting date), `created_date`, `last_edited_date` (set on every row; citywide maximum 2026-06-25). |
| Pagination | Supported: `advancedQueryCapabilities.supportsPagination: true`. `resultOffset=0` and `5` with `resultRecordCount=5` and `orderByFields=OBJECTID ASC` returned disjoint pages (`14747, 46012..46015` then `46016, 46085..46088`) with `exceededTransferLimit: true`. |
| `maxRecordCount` | 2000 (equal to the adapter's `PAGE_CAP`). Citywide count 365,656. |
| `editingInfo.lastEditDate` | **Absent** (no `editingInfo` in the layer JSON). The adapter's layer-edit-date vintage fallback therefore never applies here; the vintage comes from `INSPCTDATE` (median 2022). Per-row `last_edited_date` exists if a better vintage is wanted. The layer metadata date 2026-06-30 is in the RISK-001 notes. |
| `objectIdField` | Not a top-level key in this layer's JSON. The adapter falls back to the field of type `esriFieldTypeOID` (`OBJECTID`), which is what the region config uses. |
| Height and units | `HEIGHT_FT` (SmallInteger, feet; values 10 to 70 in the recording bbox in steps of 10, maximum 100 citywide) and `DBH_IN` (inches). Null on 37% of `AB` rows (uninspected). Heights are rounded steps, not measurements. |
| Geometry | Point `{x, y}` in WGS84 with `outSR=4326`. The server's envelope test is slightly loose: 11 of 220 returned points were up to about 1 m outside the bbox on the north edge; the adapter drops them and warns. |

### stiles/la-trees (`la_county_trees`)

| Item | Answer |
|---|---|
| Layout | The repository (`https://github.com/stiles/la-trees`) has per-city folders under `data/municipalities/<city>/` (GeoJSON, plus shapefile parts or CSV for big cities) and a flat copy in `data/municipalities/all/<city>.geojson`. The county compilation is **not** in the repo. It is on S3 (the URL above, README link "All LA street tree locations", 626,629,879 bytes). LA city has its own S3 file, `https://stilesdata.com/trees/los-angeles/la_street_trees_latlon.geojson` (165,657,142 bytes, last modified 2026-05-03). |
| County file format | GeoJSON, CRS84 (WGS84 lon/lat), one feature per line inside a `FeatureCollection`, all points. Properties: `id, place, species, ispalm, mexfanpalm, jacaranda, pine, oak, magnolia, category, camphor, ash, crepemyrtle`. Booleans are mixed: `ispalm`, `mexfanpalm`, `pine`, `oak`, `magnolia` are the strings `"True"/"False"`; `jacaranda`, `camphor`, `ash`, `crepemyrtle` are JSON booleans. **No height, DBH, status or date field.** The file is ordered by `category` in blocks, so palm rows are not at the head (the first 5,172 rows contain none; 881 palm rows appear in the ranges sampled). |
| Species strings | `species` holds **common names only**, title case, e.g. `Mexican Fan Palm`, `Canary Island Date Palm`, `Queen Palm`, `California Fan Palm`, `King Palm`, `Guadalupe Palm`, `Windmill Palm`, `Triangle Palm`, `Date Palm`, `Coconut Palm`, `Palm Species`, `Palm Tree`, `Med Fan Palm`, `Sago Palm` (a cycad), `Fishtail Wine Palm`. Non-tree rows are in the same field: `Vacant`, `Vacant Planting Site - Large/Medium/Small`, `Vacant Site`, `Vacant/Inadequate Spacing`, `Vacant/Ok To Replant`, `Stump`, `Stump - Not Accessible`, `Dead Tree`, `Unknown`; the existing markers cover them. |
| `id` stability | `id` is a 0-based row index of the compilation (the head rows are 0, 1, 2, ...), not a city tree id. It is stable only while the file is unchanged. The S3 object has not changed since 2024-05-31 (`Last-Modified`), but nothing says it is versioned, so pin by ETag and treat `id` as unstable across releases. The per-city files keep the cities' own ids (Santa Monica: `OBJECTID`). |
| Per-city files differ | The Santa Monica file is in **EPSG:2229** (California State Plane V, feet; `crs` is declared) with `lat`/`lon` properties as well. Fields: `OBJECTID, SpeciesID, DBH, height, species` (common name, upper case), `BotanicalN` (Latin), `Address, OnStreet, ...`. `height` and `DBH` are class strings (`01-15`, `15-30`, `30-45`, `45-60`, `60+`, `---`; `0-6`, `07-12`, `13-18`, `19-24`, `25-30`, `31+`). Units are not stated in the file; feet and inches are the likely reading. `parse_height` turns `15-30` into the midpoint and `60+` into `None`. The adapter handled the declared CRS (332 trees from the OGR bbox filter, equal to the `lat`/`lon` property count). |
| Memory on the big file | Not run on the real 627 MB file (not downloaded). Measured peak working-set growth of `GeoJsonFileAdapter.fetch` (Windows, Python 3.14, pyogrio): +18.6 MB on the real 25.7 MB Santa Monica file (1.0 s) and +48 MB on a 289 MB synthetic file (the real county-format rows repeated 24 times, 35 s). That extrapolates to roughly +100 MB and about 75 s on the 627 MB file: low memory, but every call rescans the file, so convert to GeoPackage or FlatGeobuf if it is read often. The extrapolation is an estimate. |

### StreetsLA

The only machine-readable endpoint found is the TreeKeeper GeoServer WFS used by la-trees' `scripts/fetch_la_treekeeper.py` (`https://geola.daveytreekeeper.com/geoserver/Treekeeper/ows`, layer `Treekeeper:streetsla_UFDSpeciesLabel`, `site_id`, `tree_common`, coordinates in EPSG:2229, per the la-trees README and the region file notes). No ArcGIS FeatureServer for the street-tree inventory was found; the LA GeoHub item "Trees (Bureau of Street Services)" is described as a historical inventory that is not maintained (RISK-001). The WFS was not queried in this task (no adapter type exists for it). Its LA-city rows are already in the county compilation and in `la_street_trees_latlon.geojson`.

### Height fields

San Diego has `HEIGHT_FT` (feet) and `DBH_IN`. Santa Monica has class strings. The county compilation has none. OSM tree nodes can carry `height` (metres by OSM convention) and `diameter_crown`: 29 of 31 species-tagged San Diego nodes have both, but `OsmTreesAdapter` ignores them and the `height` value units are not enforced by OSM. Config `height_units` is `ft` for San Diego.

### Real species and status strings (tables)

Distinct values read: all 613 `SPECIES_NAME` and 810 `COMMON_NAME` values of the San Diego layer (`returnDistinctValues`, plus the 1,060 distinct pairs), the Santa Monica clip, 429 distinct `species` values from the county sample, and the OSM tags. Added to `palmscan/data`: aliases for real palms that were not matched or mis-matched (`bottle palm` and `hyophorbe lagenicaulis` as `palm_unknown`, because genus Hyophorbe has no registry key or size default and adding one is SCAN-002/SCAN-009 scope; `pigmy date palm`, `filibusta palm`, `clustered fishtail palm`, `fishtail wine palm`, `giant fishtail palm`, `ribbon fan palm`, `hesper palm`, `hybrid date palm`, `puerto rican hat palm`, `palmetto species`, `paradise palm`, `med fan palm`); "palm"-named or palm-genus-named non-palms (`madagascar palm`, `pachypodium lamerei`, `pony tail palm`, and `phoenix mesquite`, which the genus rule had turned into a Phoenix palm); and the status code `rm` (whole-string match, so `Dormant` is not hit). Left as is: `Paradise Palm` maps to `palm_unknown` because those rows carry no Latin name; `Med Fan Palm` is an inference from the abbreviation.

### Microsoft Global ML Building Footprints (answer only, read 2026-11-22)

Source: https://github.com/microsoft/GlobalMLBuildingFootprints.
- Index: `https://bfppub.blob.core.windows.net/%24web/2026-11-12/dataset-links.csv` (6,333,409 bytes), columns `Location,QuadKey,Url,Size,UploadDate`; the page says it covers data from 2022-07-05 to 2026-11-12.
- Tiles: one file per country and level-9 quadkey, e.g. `.../2026-11-12/global-buildings.geojsonl/RegionName=UnitedStates/quadkey=023013221/part-00065-....c000.csv.gz`. The extension is `.csv.gz` but the content is **GeoJSON lines**; decompress and rename (the repo has `scripts/make-gis-friendly.py`).
- Tiles are big: the San Diego bbox centre falls in quadkey `023013221` (78.1 MB) and the LA Westside centre in `023012311` (171.0 MB), compressed.
- Properties named on the page: `height` (metres, null when not measured) and `confidence` (0 to 1, null when not measured); polygons in EPSG:4326. The bbox-to-tile download could be automated from the index (compute the level-9 quadkey, look it up, stream the file), but this was not built or tested, and no tile was downloaded. `fetch_buildings` reads a local GeoJSON/GeoJSON-lines/GPKG, which fits once a tile is decompressed.
- License: CDLA Permissive 2.0 (page statement).

## Differences from the plan (for the plan owner)

1. San Diego **has** a status field, `MAPNG_STAT_CD`; the plan and region file said there was none. Removed rows are 25% of the layer.
2. `editingInfo.lastEditDate` is absent; the "layer_edit_date" vintage basis is never used for San Diego.
3. `SPECIES_NAME` is null on about 37% of standing rows (uninspected), so common-name fallback is essential.
4. The la-trees county `id` is a row index (the plan guessed this), and the county file has no height, status or date. Per-city files use other CRSs (EPSG:2229) and class-string sizes.
5. The Microsoft index is a CSV of country and level-9 quadkey tiles of `.csv.gz` GeoJSON lines, 78 to 171 MB per tile for the two example regions; a bbox download is feasible but heavy.
6. OSM has almost no species-tagged trees in the San Diego example region (31 in the whole region box, 29 of them Jubaea in one spot); the 400 m recording bbox has none.
