# Build report: palmfix-san-diego-coastal

- Result: **PASS**
- Region: san-diego-coastal
- Package: palmfix-san-diego-coastal
- Version: 1.3.0+data2026-11
- Package version: 1.3.0
- Generator version: 1.3.0
- Data version: 2026-11
- Placement: static
- Models: library

## Inputs

| Input | Path | SHA-256 |
| --- | --- | --- |
| buildings | build/scan/san-diego-coastal/buildings.geojson | bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb |
| config | regions/san-diego-coastal.yaml | dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd |
| manifest | assets/manifest.json | cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc |
| palms | build/scan/san-diego-coastal/palms.geojson | aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa |
| templates | palmgen/templates | eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee |

## Counts

| Count | Value |
| --- | --- |
| palms_in | 3 |
| dropped_outside_bbox | 0 |
| dropped_by_mask | 0 |
| dropped_in_building | 0 |
| radius_defaulted | 1 |
| radius_clamped | 0 |
| clusters | 0 |
| clusters_split | 0 |
| polygons | 2 |
| polygon_parts_from_clip | 0 |
| objects | 3 |
| scale_clamped | 0 |
| species_fallback | 0 |
| height_missing | 0 |
| tiles | 2 |

## Masks

| Mask | Kind | Palms dropped | Polygons clipped |
| --- | --- | --- | --- |
| airport-lindbergh | airport | 0 | 1 |
| park-balboa | mask | 1 | 0 |

## Variants

| Species | Variant | Count | Scale min | Scale median | Scale max |
| --- | --- | --- | --- | --- | --- |
| Phoenix | canariensis | 1 | 0.9500 | 0.9500 | 0.9500 |
| Washingtonia | robusta | 2 | 0.9000 | 1.0000 | 1.1000 |

## Tiles

| Tile | Polygons | Objects | BGL |
| --- | --- | --- | --- |
| n32p78_w117p26 | 1 | 1 | tile_n32p78_w117p26.bgl |
| n32p79_w117p26 | 1 | 2 | tile_n32p79_w117p26.bgl |

## Timings

| Stage | Seconds |
| --- | --- |
| generate_s | 1.250 |
| compile_s | 12.346 |
| checks_s | 0.500 |
| total_s | 14.096 |

## fspackagetool

| Field | Value |
| --- | --- |
| path | C:/Program Files/fspackagetool/fspackagetool.exe |
| command | C:/Program Files/fspackagetool/fspackagetool.exe palmfix-san-diego-coastal.xml -outputdir out -nopause |
| exit_code | 0 |
| log_path | logs/fspackagetool.log |
| warning_lines | 0 |
| error_lines | 0 |

## Checks

| Check | Expected | Actual | Passed |
| --- | --- | --- | --- |
| bgl_per_tile | 2 | 2 | yes |
| exit_code_zero | 0 | 0 | yes |
| no_error_lines_in_log | 0 | 0 | yes |
| object_count_matches | 3 | 3 | yes |
| polygon_count_matches | 2 | 2 | yes |

## Warnings

| Code | Count | Examples |
| --- | --- | --- |
| RADIUS_DEFAULTED | 1 | p1 has no crown diameter |
| SCALE_CLAMPED | 2 | p2 scale 1.30 clamped to 1.15; p3 scale 0.80 clamped to 0.85 |
