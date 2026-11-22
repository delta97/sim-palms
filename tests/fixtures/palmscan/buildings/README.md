# Building footprint fixtures (SCAN-006)

Both files are synthetic, hand-built around (-117.2531, 32.7893) (San Diego) from metre offsets
in EPSG:32611. No real OSM or Microsoft data is stored here. Test bbox:
`[-117.2540, 32.7885, -117.2520, 32.7905]`.

## `overpass_buildings.json`

Shape of an Overpass `out geom;` JSON response (`elements` with inline `geometry`). Generated
2026-11-22; no endpoint was queried. Contents:

| Element | What it tests | Expected |
|---|---|---|
| way 1001 | closed 20 m x 20 m square | Polygon, 400 m2, `way/1001` |
| way 1002 | unclosed way | skipped, counted |
| relation 2001 | multipolygon: outer ring split over ways 1003 + 1004, inner way 1005 (10 m courtyard) | one Polygon with one interior ring, 1500 m2, `relation/2001` |
| ways 1003-1005 | untagged relation members | not buildings on their own |
| way 1006 | self-intersecting bowtie | repaired to MultiPolygon, 50 m2 |
| relation 2002 | outer member with no inline geometry | skipped, counted |
| node 3001 | not a building | ignored |

OSM data is ODbL 1.0, copyright OpenStreetMap contributors (`docs/licenses/data-sources.md`).

## `ms_footprints_sample.geojsonl`

Microsoft Global ML Building Footprints style: one GeoJSON Feature per line, properties
`height` and `confidence` (both -1.0 when unknown). Rows 0-2 are inside the test bbox, rows 3 and
4 are about 5 km away, row 5 is a bowtie that is repaired. Expected ids `msbf:0`, `msbf:1`,
`msbf:2`, `msbf:5` (GDAL feature id, 0-based).

VERIFY (for SCAN-007): the real distribution format of the Global ML Building Footprints (per
quadkey files, compression, property names) was not checked here. The adapter reads any OGR
file at `sources.buildings_path` (GeoJSON, GeoJSON lines, GPKG). The data is CDLA Permissive 2.0.
