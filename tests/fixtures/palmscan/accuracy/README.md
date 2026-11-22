# Accuracy fixtures (SCAN-029)

All files here are SYNTHETIC. Coordinates are Null Island (lon 0.00 to 0.02, lat 0.00 to 0.02),
not a real street, and the palms and labels are invented for tests.

- `pred.geojson`: six palms (`palms.geojson` shape, valid under `palmcore.contract`). Five lie in
  the labelled area, one lies outside it.
- `pred_empty.geojson`: a valid palms file with no features.
- `T9/`: a TEST-009 site folder (`ground_truth.geojson`, `labeled_area.geojson`, `meta.yaml`) with
  six labelled palms, one of them low confidence.

Read by `tests/unit/palmscan/test_scan_accuracy.py` through `palmscan.qa.accuracy.evaluate_site`
with `sites_root` set to this folder. Site id `T9` is used because TEST-009 site ids must match
`T[0-9]+`; the folder name `site_TX` in the task text was not valid.
