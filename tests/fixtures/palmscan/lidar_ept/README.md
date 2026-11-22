# lidar_ept fixtures (SCAN-020)

Synthetic, hand-made files. Nothing here is real USGS data.

- `boundaries_sample.geojson`: three rectangular MultiPolygon features with the property names
  seen in the real boundaries index on 2026-11-22 (`name`, `id`, `count`, `url`). `SYN_SanDiego_2014`
  (lon -117.30..-117.10, lat 32.60..32.80) overlaps `SYN_SanDiego_2018` (lon -117.20..-117.14,
  lat 32.70..32.76); `SYN_Elsewhere_2020` is near Los Angeles. URLs are `example.test`.
- `ept_sample.json`: a minimal `ept.json` with the `srs` block shape of the real San Diego file
  (`authority` EPSG, `horizontal` 3857). The real files also carry a long `wkt`; it is omitted.
- `expected_pipeline.json`: golden PDAL pipeline for tile `e485000_n3620000` of the
  `SYN_SanDiego_2018` dataset in EPSG:32611, noise classes 7 and 18, output `out/tile.laz`.
  It is checked by hand, not by PDAL; if the pipeline format changes on purpose, rewrite it from
  `build_pipeline` output and review the diff.
