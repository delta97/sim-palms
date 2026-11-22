# End-to-end fixture region (SCAN-013)

Synthetic data, generated 2026-11-22; no real inventory or footprints. Positions are metre
offsets (east, north) from (-117.2531, 32.7893). Region paths resolve against
`tests/fixtures/palmscan/`.

`e2e_trees.geojson` (source `e2e_trees`, 15 records):

| id | offset | What it tests |
|---|---|---|
| 1 | (0, 0) | genus-only `Washingtonia`; second source has a species-level duplicate 1.1 m away |
| 2 | (30, 0) | W. robusta; a footprint lies 6 m away but does not conflict |
| 3, 4, 11, 12, 13, 14, 15 | various | plain palms, inventory heights and defaults |
| 5 | (-60, -30) | genus-only `Brahea` (key `brahea_sp`) |
| 6 | (90, 0) | King palm next to a footprint: `building_conflict` |
| 7 | (-100, 0) | `Vacant Site`: non-tree reject |
| 8 | (0, 50) | `Quercus agrifolia`: not a palm |
| 9 | (-60, 60) | `Palm`: `palm_unknown`, gets a prior sample |
| 10 | (-80, 100) | inside the `e2e_no_go` mask |

`e2e_trees_second_source.geojson` (source `e2e_second`): the duplicate of record 1 and one
separate palm. `e2e_buildings.geojson`: three footprints (conflicting, near but clear, far away).
