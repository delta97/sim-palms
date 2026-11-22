# osm_overpass fixtures

Synthetic Overpass API JSON written by hand for SCAN-005 tests. Not real OpenStreetMap data;
ids, coordinates and tags were invented. The response shape (`elements`, `remark`) follows
the Overpass API.

- `trees_response.json`: 8 `natural=tree` nodes (ids 1001-1008). Tagged: 1001 (species and
  `species:en`), 1002 (non-palm), 1004 (genus only), 1005 (genus beats taxon, per the species, genus, taxon, species:en order), 1006
  (`species:en` only). Untagged: 1003, 1007 (blank species), 1008 (no tags). Expected: 5
  records, 3 dropped.
- `runtime_error.json`: HTTP 200 body with a `remark` containing `runtime error`.

## Licence

OpenStreetMap data is (c) OpenStreetMap contributors, available under the Open Database
License (ODbL) 1.0: https://www.openstreetmap.org/copyright. See
`docs/licenses/data-sources.md` section 4 (RISK-001).
