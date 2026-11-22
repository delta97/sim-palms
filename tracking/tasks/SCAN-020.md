---
id: SCAN-020
title: "USGS 3DEP EPT LiDAR adapter (PDAL pipeline, tiles, cache)"
status: todo
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w13-lidar-ept-adapter"
depends_on: [SCAN-003]
requires: [none]
agent: lidar-analyst
estimate_h: 4
touches: [palmscan/sources/lidar_ept.py, tests/unit/palmscan/test_scan_lidar_ept.py, tests/fixtures/palmscan/lidar_ept/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`palmscan/sources/lidar_ept.py` selects the 3DEP EPT dataset(s) covering a bbox, plans buffered 500 m tiles, builds and runs a PDAL pipeline per tile, caches the result as LAZ under `data/lidar/`, and exposes points through a `PointSource` the pipeline can swap for a fake.

## Context

- Spec: plan_ref section W13.
- Facts not yet confirmed (VERIFY in SCAN-021): boundaries index URL and property names, dataset naming/year parsing, EPT native SRS (read `srs` from `ept.json` rather than assuming EPSG:3857), class availability. Code must read these from data, not hard-code them; isolate the parsing in small functions SCAN-021 can adjust.
- PDAL Python bindings need the PDAL C++ library (often conda). Tests that execute PDAL use `pytest.importorskip("pdal")`; everything else (pipeline JSON, tiling, dataset selection) runs without PDAL.
- The `lidar` extra in `pyproject.toml` was added by SCAN-001.

## Steps

1. Dataclasses `EptDataset`, `LidarTile`; `PointSource` protocol; `EptPointSource(cfg, cache, http)` implementing it.
2. `load_boundaries(cache, http)` (cache namespace `lidar_boundaries`, 30-day max age) and `parse_boundaries(geojson) -> list[EptDataset]` with year parsed by `_(\d{4})` from the name.
3. `select_datasets(datasets, bbox, forced)`: intersecting footprints, newest year wins on overlap, `forced` overrides, none -> `SourceError`.
4. `plan_tiles(bbox, crs, tile_size_m=500, buffer_m=20)`: tiles snapped to multiples of tile size in local UTM; `tile_id = e{x}_n{y}`.
5. `build_pipeline(ds, tile, crs, noise_classes, out_path) -> dict` exactly as in W13 (bounds transformed to the EPT SRS read from `ept.json`).
6. `fetch_tile(...)`: run PDAL (`pdal.Pipeline(json.dumps(p)).execute()`), write `data/lidar/<dataset>/<tile_id>.laz` + `.meta.json`; skip if cached unless refresh; offline + missing -> `CacheMiss`.
7. `read_points(path) -> np.ndarray` with fields `X Y Z Classification ReturnNumber NumberOfReturns`.
8. Fixtures: `boundaries_sample.geojson` (3 synthetic datasets, two overlapping with different years), `ept_sample.json` (minimal `ept.json` with an `srs` block), `expected_pipeline.json`, `README.md`.
9. Tests: dataset selection cases, tile count and ids for a 1.2 km bbox, pipeline golden dict, cache skip logic (PDAL call monkeypatched), PDAL execution test skipped when PDAL is absent.

## Acceptance criteria

- [ ] Newest dataset chosen on overlap; `lidar.datasets` override respected; no coverage raises `SourceError`.
- [ ] Pipeline JSON matches the golden file.
- [ ] Cached tiles are not refetched; offline miss raises `CacheMiss`.
- [ ] Test suite passes with and without PDAL installed (PDAL tests skipped when absent).

## Verification

```bash
pytest tests/unit/palmscan/test_scan_lidar_ept.py -q
python -c "import pdal" 2>/dev/null && echo "pdal present" || echo "pdal absent: execution tests skipped"
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
