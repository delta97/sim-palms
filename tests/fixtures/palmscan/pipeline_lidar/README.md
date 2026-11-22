# LiDAR end-to-end fixture (SCAN-028)

Synthetic data, generated 2026-11-22; no real inventory, footprints, point cloud or labels.
Region paths resolve against `tests/fixtures/palmscan/`. Used by
`tests/unit/palmscan/test_scan_pipeline_lidar.py`, which builds the point cloud in code and
serves it through a fake PDAL runner (no PDAL, no network).

Positions are metres (easting, northing) in EPSG:32611. The ground rises 2 cm per metre of
easting from 10 m at easting 476000. `lidar-e2e.yaml` plans nine 200 m tiles (10 m buffer), so the
tile edges at easting 476400 and northing 3627800 / 3628000 cut through the scene, and sets
`rules.crown_min_m: 3.5` (smoothing widens the thinnest synthetic crown to 3.2 m).

| Scene object | Where | Expected outcome |
|---|---|---|
| Cone A, 14 m, radius 2.6 m | (476300, 3627900) | matched to inventory palm 1 (1.2 m east of it): `inventory+lidar` |
| Cone B, 11 m, radius 2.4 m | (476399, 3627850), 1 m inside a tile edge | `lidar`, reported once |
| Cone C, 18 m, radius 3.0 m | (476230, 3627750) | `lidar` |
| Thin cone, 12 m, radius 1.3 m | (476250, 3627950) | rejected `crown_small` (3.2 m crown) |
| Flat dome, 10 m, radius 8 m | (476440, 3627900) | rejected `crown_large;ratio` |
| 3 x 3 cones, 12 m, 3.5 m apart | from (476150, 3628100) | six crowns, all rejected `not_isolated` |
| Cone, 14 m, inside a footprint | (476430, 3628060) | rejected `building` (footprint 476420-476440 x 3628050-3628070, roof 1.5 m, class 6) |

Files:

- `lidar_trees.geojson` (source `lidar_trees`): palm 1 (Washingtonia robusta, next to cone A) and
  palm 2 (Phoenix canariensis at (476350, 3627790), no LiDAR crown: `inventory`, ground from the DTM).
- `lidar_buildings.geojson`: the one footprint above.
- `T8/`: a TEST-009 site folder (`ground_truth.geojson`, `labeled_area.geojson`, `meta.yaml`): five
  labelled palms (the four palms above plus one at (476450, 3627760) that nothing covers), in an
  area of easting 476100-476520 and northing 3627700-3628000. Expected: combined TP 4 FP 0 FN 1,
  lidar_only TP 3 FP 0 FN 2, phase1_inventory TP 4 FP 0 FN 0.
