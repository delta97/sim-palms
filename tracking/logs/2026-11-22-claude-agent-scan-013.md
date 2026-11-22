# Session log: 2026-11-22, claude-agent, scan-013

- **Started / ended:** 2026-11-22 (single session)
- **Agent / model / person:** claude-agent
- **Branch / worktree:** task/scan-013-palmscan-run-pipeline-and-cli-end-to-end, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-013
- **Tasks:** SCAN-013 (in_progress -> review)

## Goal

Wire the merged Phase 1 stages into `palmscan run` and `palmscan priors`, end to end on offline fixtures.

## What changed

- `palmscan/pipeline.py`: `RunOptions`, `RunResult`, `run`, `inventory_stages` (stages 2 to 4, shared with `priors`), `species_level`. Writes palms, buildings, priors, QA files and `run.json` (also on failure).
- `palmscan/cli.py`: `run` and `priors`; output dir `--out` > `palmscan.output_dir` > `build/scan/<region>`; `eval` still exits 1.
- `tests/fixtures/palmscan/regions/`: `e2e.yaml`, `e2e_trees.geojson`, `e2e_trees_second_source.geojson`, `e2e_buildings.geojson`, README.
- `tests/unit/palmscan/test_scan_pipeline.py` (10 tests); `test_scan_cli.py` no longer expects run/priors to be unimplemented.
- `plans/detailed/02-detection-pipeline.md` W11: `generated_at`, CacheMiss re-raise, priors filter, notices.

## Verification

`pytest -q`: 1544 passed, 5 skipped. `ruff check .`, `ruff format --check .`, `mypy`: clean. `palmscan run --region e2e ... --offline` exit 0 and all seven output files present.

## Decisions and findings

- `ingest_inventory` wraps adapter errors as `SourceError`, hiding `CacheMiss` (exit 5 became 4). The pipeline re-raises a wrapped `CacheMiss`. A cleaner fix is in `ingest.py` (preserve the subclass); left alone as outside `touches`.
- `compute_priors` accepts `brahea_sp` style keys (they match its regex), and genus-only names carry a default species. The pipeline feeds it species-level palms only.
- Region `id_prefix` must match `[a-z]{2,6}`; the fixture uses `ete`.
- Paths in a region YAML resolve against the parent of the regions dir, so fixture paths read `regions/e2e_trees.geojson`.
- `buildings.geojson` has an extra top-level `notices` map (licence and attribution by source).
- Byte-identical output needs a fixed `generated_at`: set `SOURCE_DATE_EPOCH` (the CLI has no flag for it).

## Open issues

- LiDAR stage (`point_source`, stage 5) is a placeholder for SCAN-028; `--eval-site` only warns.

## Handoff: next steps

1. Review SCAN-013; then SCAN-100 (Phase 1 deliverable run, needs network and a human).
