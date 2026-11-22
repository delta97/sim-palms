---
id: SCAN-028
title: "Wire LiDAR stages into palmscan run, QA and eval"
status: todo
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w20-lidar-pipeline-integration"
depends_on: [SCAN-013, SCAN-020, SCAN-024, SCAN-025, SCAN-027, SCAN-029]
requires: [none]
agent: lidar-analyst
estimate_h: 4
touches: [palmscan/pipeline.py, palmscan/cli.py, palmscan/qa/summary.py, palmscan/qa/gpkg.py, palmscan/qa/rejects.py, tests/unit/palmscan/test_scan_pipeline_lidar.py, tests/fixtures/palmscan/pipeline_lidar/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`palmscan run` executes the full Phase 4 chain (EPT tiles, CHM, peaks, palm rules, merge, tree or rules classification, region-median heights, ground elevation) and writes the LiDAR QA layers, classifier report and accuracy files; `palmscan eval` works standalone.

## Context

- Spec: plan_ref section W20 (steps 1-7) and the stage order in W11.
- Flags: `--no-lidar`, `--only inventory|lidar`, `--truth PATH`; `eval` subcommand per "CLI".
- The e2e test injects a fake `PointSource` with synthetic points (no PDAL, no network).
- Do not change module APIs from SCAN-020 to SCAN-027; if one is insufficient, note it in the Log and add a minimal backwards-compatible parameter.

## Steps

1. In `pipeline.run`: if `sources.lidar == "3dep_ept"` and not `no_lidar`, build `EptPointSource` (or use the injected `point_source`); loop tiles one at a time: `build_chm` -> `find_peaks` -> `segment_crowns` -> `crown_stats`; collect candidates and keep each tile's DTM only long enough to sample ground for inventory palms in that tile.
2. `apply_palm_rules` with the buildings frame; `merge`; `train` (or load `classify.tree_model_path`); write `species_tree.json` when used; `classify(palms, priors, model)`.
3. `assign_sizes(..., region_medians)`; `data_vintage.lidar` and `ground_elev_m` set.
4. `--only lidar`: skip ingest; `--only inventory` or `--no-lidar`: skip LiDAR.
5. QA: pass candidates/crowns to `write_qa_gpkg`; add LiDAR rejects to CSV; Classifier section from `TrainReport`; LiDAR vintage in grid.
6. `--truth`: `evaluate` + `accuracy.json` + Accuracy section. `cli eval`: load palms and truth, print the targets table, write `--out` JSON.
7. `-vv`: debug GeoTIFFs under `<out>/debug/`.
8. Fixtures in `tests/fixtures/palmscan/pipeline_lidar/`: region YAML, two-record inventory, buildings file, tiny truth file. Synthetic point generator in the test module.
9. Tests: mixed `detected_by` counts, reject reasons (`not_isolated`, `crown_small`, `building`), schema validity, rerun determinism, `--only lidar` drops inventory palms, `eval` exit 0 with expected numbers.

## Acceptance criteria

- [ ] E2E with fake `PointSource` yields `inventory+lidar`, `inventory` and `lidar` palms as designed, and the expected rejects in `qa_rejects.csv`.
- [ ] `qa_map.gpkg` has `lidar_candidates`; `qa_summary.md` has Classifier and Accuracy sections.
- [ ] `palmscan eval --palms ... --truth ...` prints the targets table and writes JSON.
- [ ] Phase 1 tests (SCAN-013) still pass unchanged.

## Verification

```bash
pytest tests/unit/palmscan -q
palmscan eval --palms tests/fixtures/palmscan/accuracy/pred.geojson --truth tests/fixtures/palmscan/accuracy/truth.geojson --out /tmp/acc.json; echo "exit=$?"
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
