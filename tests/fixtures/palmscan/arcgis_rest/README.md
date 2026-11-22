# arcgis_rest fixtures

Synthetic. Not recorded from any live service; names, ids, coordinates and dates were invented
for SCAN-004 tests. The JSON shape follows the Esri REST JSON format. Recording real San Diego
layer 20 responses (and confirming its field names, `maxRecordCount`, pagination support and
`lastEditDate`) is SCAN-007's job: VERIFY there.

- `layer_info.json`: layer info with `maxRecordCount: 3`, `supportsPagination: true`,
  `editingInfo.lastEditDate` 2021-01-01 (epoch ms) and San Diego style field names.
- `layer_info_nopaging.json`: same, `supportsPagination: false`.
- `query_page_0.json`: full page (ids 101-103), `exceededTransferLimit: true`.
- `query_page_1.json`: partial page (ids 104-105; 105 has empty attributes except the id).
- `ids_only.json`: `returnIdsOnly=true` answer, ids 101-105.
- `query_by_ids.json`: all five features; the test transport returns the requested subset.
- `error.json`: an ArcGIS error body (real servers send these with HTTP 200).
- Test bbox `[-117.28, 32.70, -117.15, 32.82]`; all points lie inside it.
