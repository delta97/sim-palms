# Session log: 2026-11-22, claude-agent, scan-028

- **Started / ended:** 2026-11-22 (local) / 2026-11-22
- **Agent / model / person:** claude-agent (lidar-analyst role)
- **Branch / worktree:** task/scan-028-wire-lidar-stages-into-palmscan-run-qa-a, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-028
- **Tasks:** SCAN-028 (in_progress -> review)

## Goal

Wire the merged Phase 4 modules (EPT source, CHM, peaks, palm rules, merge, species classifier, accuracy) into `palmscan run`, the QA files and `palmscan eval`, and prove it offline end to end.

## What changed

- `palmscan/pipeline.py`: LiDAR stage (tiles, rules, merge, classify, sizes, ground elevation), eval-site CHM, accuracy step, new QA inputs, optional-output cleanup.
- `palmscan/cli.py`: `eval` implemented, `--sites-root`, `-vv` debug rasters, repo root for the evaluator.
- `tests/unit/palmscan/test_scan_pipeline_lidar.py`, `tests/fixtures/palmscan/pipeline_lidar/`: synthetic scene, fake PDAL runner, 18 tests, fixture README.
- `tests/unit/palmscan/test_scan_pipeline.py`, `test_scan_cli.py`: two Phase 1 tests rewritten (the LiDAR warning and the eval stub no longer exist).
- `plans/detailed/02-detection-pipeline.md`: "As built" notes under W20.
- `qa/summary.py`, `qa/gpkg.py`, `qa/rejects.py` needed no change: they already took the LiDAR inputs.

## Verification

- `pytest -q`: 1794 passed, 3 skipped (PDAL binding, network). `ruff check .`, `ruff format --check .`, `mypy`: clean.
- `palmscan eval --palms tests/fixtures/palmscan/accuracy/pred.geojson --site T9 --sites-root tests/fixtures/palmscan/accuracy --out <json>`: table printed, exit 0.

## Decisions and findings

- Smoothing (sigma 1 px) widens any crown to about 3 m, so the fixture region sets `rules.crown_min_m: 3.5` to get a `crown_small` reject from a physical object. Real tuning is SCAN-030.
- A full 500 m tile CHM with sparse ground returns spends about a second in the Delaunay DTM fill (`chm._linear_fill`); the fixture uses 200 m tiles and one ground return per cell.
- Tile cache is keyed by dataset, buffered bounds, CRS and noise classes, so changing `tile_size_m` re-reads tiles.
- `-vv` debug rasters and `eval/<site>/chm.tif` are not listed in run.json `outputs` (directories).

## Open issues

- Real PDAL and real 3DEP data are untested here (SCAN-021, SCAN-030).
- `ShapeModel.name` protocol vs `TreeModel.name` ClassVar (cast in pipeline); could be fixed in SCAN-026/027 code.

## Handoff: next steps

1. Review SCAN-028; then SCAN-030 can run `palmscan run -vv` and `palmscan eval` on the real sites.
