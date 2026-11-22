---
id: SCAN-028
title: "Wire LiDAR stages into palmscan run, QA and eval"
status: in_progress
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w20-lidar-pipeline-integration"
depends_on: [SCAN-013, SCAN-020, SCAN-024, SCAN-025, SCAN-027, SCAN-029]
requires: [none]
agent: lidar-analyst
estimate_h: 4
touches: [palmscan/pipeline.py, palmscan/cli.py, palmscan/qa/summary.py, palmscan/qa/gpkg.py, palmscan/qa/rejects.py, tests/unit/palmscan/test_scan_pipeline_lidar.py, tests/unit/palmscan/test_scan_pipeline.py, tests/unit/palmscan/test_scan_cli.py, tests/fixtures/palmscan/pipeline_lidar/]
owner: claude-agent
branch: task/scan-028-wire-lidar-stages-into-palmscan-run-qa-a
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-028"
updated: 2026-11-22
---

## Goal

`palmscan run` executes the full Phase 4 chain (EPT tiles, CHM, peaks, palm rules, merge, tree or rules classification, region-median heights, ground elevation) and writes the LiDAR QA layers, classifier report and accuracy files; `palmscan eval` works standalone.

## Context

- Spec: plan_ref section W20 (steps 1-7) and the stage order in W11.
- Flags: `--no-lidar`, `--only inventory|lidar`, `--eval-site SITE`; `eval` subcommand per "CLI" (`eval --palms PATH --site SITE [--profile NAME] [--out PATH]`). Accuracy is computed by TEST-010 via SCAN-029; palmscan only produces inputs and runs it.
- The e2e test injects a fake `PointSource` with synthetic points (no PDAL, no network).
- Do not change module APIs from SCAN-020 to SCAN-027; if one is insufficient, note it in the Log and add a minimal backwards-compatible parameter.

## Steps

1. In `pipeline.run`: if `sources.lidar == "3dep_ept"` and not `no_lidar`, build `EptPointSource` (or use the injected `point_source`); loop tiles one at a time: `build_chm` -> `find_peaks` -> `segment_crowns` -> `crown_stats`; collect candidates and keep each tile's DTM only long enough to sample ground for inventory palms in that tile.
2. `apply_palm_rules` with the buildings frame; `merge`; `train` (or load `classify.tree_model_path`); write `species_tree.json` when used; `classify(palms, priors, model)`.
3. `assign_sizes(..., region_medians)`; `data_vintage.lidar` and `ground_elev_m` set.
4. `--only lidar`: skip ingest; `--only inventory` or `--no-lidar`: skip LiDAR.
5. QA: pass candidates/crowns to `write_qa_gpkg`; add LiDAR rejects to CSV; Classifier section from `TrainReport`; LiDAR vintage in grid.
6. `--eval-site SITE`: `evaluate_site` (SCAN-029) + `accuracy.json` + Accuracy section; also write `<out>/eval/<site>/chm.tif` (CHM clipped to the site bbox) as the input for `python -m tests.accuracy.gt fill-heights <site> --chm ...` (TEST-009). `cli eval`: read palms, call `evaluate_site`, print the per-profile table, write `--out` JSON.
7. `-vv`: debug GeoTIFFs under `<out>/debug/`.
8. Fixtures in `tests/fixtures/palmscan/pipeline_lidar/`: region YAML, two-record inventory, buildings file, a tiny site folder in the TEST-009 format. Synthetic point generator in the test module.
9. Tests: mixed `detected_by` counts, reject reasons (`not_isolated`, `crown_small`, `building`), schema validity, rerun determinism, `--only lidar` drops inventory palms, `eval` exit 0 with expected numbers.

## Acceptance criteria

- [ ] E2E with fake `PointSource` yields `inventory+lidar`, `inventory` and `lidar` palms as designed, and the expected rejects in `qa_rejects.csv`.
- [ ] `qa_map.gpkg` has `lidar_candidates`; `qa_summary.md` has Classifier and Accuracy sections.
- [ ] `palmscan eval --palms ... --site ...` prints the per-profile table (from TEST-010) and writes JSON.
- [ ] Phase 1 tests (SCAN-013) still pass unchanged.

## Verification

```bash
pytest tests/unit/palmscan -q
palmscan eval --palms tests/fixtures/palmscan/accuracy/pred.geojson --site TX --out /tmp/acc.json; echo "exit=$?"   # site TX resolved under tests/fixtures/palmscan/accuracy/ in the test; real sites under tests/accuracy/
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Accuracy now runs through SCAN-029/TEST-010: --truth PATH replaced by --eval-site SITE on run and eval --palms PATH --site SITE; the pipeline also writes the eval site's CHM GeoTIFF as input for TEST-009 fill-heights. Cross-area reconciliation.
- 2026-11-22 [integrator] integrator notes: SCAN-025 merge(…, cfg.merge, cfg.dedupe_radius_m, cfg.peaks.min_height_m); SCAN-024 apply_palm_rules returns all candidates + rejects (buildings_local must be in local CRS); SCAN-027 train(merge.training, cfg.classify) -> save_model when report.used, load_model(tree_model_path) for regions without inventory, then classify(palms, priors, model); SCAN-020 adapter in progress
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-028-wire-lidar-stages-into-palmscan-run-qa-a worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-028
