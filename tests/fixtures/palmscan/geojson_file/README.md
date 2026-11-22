# geojson_file fixtures

Synthetic. Not real inventory data and not clipped from any real source; species, ids,
coordinates and dates were invented for SCAN-003 tests.

- `trees_sample.geojson` and `trees_sample.csv` hold the same 20 records (ids 101-120).
- Test bbox: `[-118.52, 33.96, -118.37, 34.09]`. Ids 117 and 118 lie outside it, so 18
  records are inside.
- 119 is a polygon in the GeoJSON (the CSV holds its representative point).
- 120 has no species. 108 is a stump, 116 vacant.
- Columns: id, species, common_name, status, height_ft, dbh_in, survey_date; the CSV adds
  `lon` and `lat`.
