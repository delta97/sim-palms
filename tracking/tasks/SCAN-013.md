---
id: SCAN-013
title: "palmscan run pipeline and CLI, end-to-end on fixtures"
status: todo
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w11-pipeline-and-cli"
depends_on: [SCAN-006, SCAN-008, SCAN-009, SCAN-010, SCAN-011, SCAN-012]
requires: [none]
agent: geo-data-engineer
estimate_h: 3
touches: [palmscan/pipeline.py, palmscan/cli.py, tests/unit/palmscan/test_scan_pipeline.py, tests/fixtures/palmscan/regions/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

`palmscan run --region <name>` runs the Phase 1 pipeline end to end and writes `palms.geojson`, `buildings.geojson`, `species_priors.yaml`, the QA files and `run.json` to `build/scan/<region>/`; `palmscan priors` prints computed priors.

## Context

- Spec: plan_ref section W11 (stage order, `RunOptions`, `RunResult`, exit codes) and "CLI".
- Phase 1 only: if `sources.lidar` is set, warn "LiDAR stage not implemented yet; inventory only" and continue. SCAN-028 adds the LiDAR stage; keep a clear hook (`point_source` parameter, stage 5 placeholder).
- Inventory source failure -> exit 4; offline cache miss -> exit 5; schema failure -> exit 3 with `palms.invalid.geojson`.
- The e2e test uses only local files (geojson_file source, Microsoft-style local buildings file, `osm_trees: false`), so it needs no HTTP fakes.

## Steps

1. `palmscan/pipeline.py`: `RunOptions`, `RunResult`, `run(cfg, opts, cache, http, adapters=None, point_source=None)` executing stages 1-9 of W11; per-stage INFO log with count and seconds; `run.json` (version, git sha, config hash, stage timings, counts, exit code).
2. Write `buildings.geojson` and `species_priors.yaml` (`priors_yaml`). `buildings.geojson` follows the ARCH-002 secondary contract (`schema_version` `1.0`, `region`, Polygon/MultiPolygon features with `building_id`, `source`) and is checked with `palmcore.contract.validate_buildings` before writing. It holds every footprint that intersects a circle of `exclusion.radius_max_m + exclusion.clip_buffer_m` around any kept palm (not only `building_conflict` ones), so palmgen's `--margin-m` override still has every footprint it could clip against.
3. `palmscan/cli.py`: implement `run` and `priors`; resolve output dir (`--out` > `palmscan.output_dir` > `build/scan/<region>`); map exceptions to exit codes; `-v/-vv` logging levels. Leave `eval` returning 1 ("available in Phase 4").
4. Fixtures in `tests/fixtures/palmscan/regions/`: `e2e.yaml`, `e2e_trees.geojson` (about 15 records: palms of several species, a vacant site, a non-palm, a genus-only, a `palm_unknown`, a pair duplicated across two sources, one inside the mask), `e2e_buildings.geojson`, `e2e_trees_second_source.geojson`.
5. Tests: e2e via `cli.main([...])` asserting exit 0, schema-valid output, palm count, one mask reject, one building conflict, every output file present, rerun byte-identical `palms.geojson`; exit 2 on a bad config; exit 5 offline with an empty cache for a URL source; exit 3 when validation is monkeypatched to fail (and `palms.invalid.geojson` exists).

## Acceptance criteria

- [ ] `palmscan run --region e2e --regions-dir tests/fixtures/palmscan/regions --out <tmp> --offline` exits 0 and writes all nine outputs listed in the plan's Outputs table (except Phase 4 files).
- [ ] Second run produces a byte-identical `palms.geojson`.
- [ ] Exit codes 2, 3, 5 behave as specified.
- [ ] `palmscan priors --region e2e ...` prints a valid `species_priors:` YAML block.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_pipeline.py -q
palmscan run --region e2e --regions-dir tests/fixtures/palmscan/regions --out /tmp/scan-e2e --data-dir /tmp/scan-e2e-data --offline; echo "exit=$?"
ls /tmp/scan-e2e   # palms.geojson buildings.geojson species_priors.yaml qa_summary.md qa_map.gpkg qa_rejects.csv run.json
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] buildings.geojson now follows the ARCH-002 secondary contract (validate_buildings) and includes every footprint within exclusion.radius_max_m + clip_buffer_m of a kept palm, so palmgen --margin-m tuning (GEN-017) never lacks a footprint; canonical output dir build/scan/<region>/ confirmed for GEN/TEST/FX. Cross-area reconciliation.
- 2026-11-22 [integrator] integrator note from SCAN-011: on ContractError from write_palms, call write_invalid(fc, out_dir) and exit 3; assign_palm_ids returns ids in input order
- 2026-11-22 [integrator] integrator note from SCAN-012: call write_qa_gpkg(..., id_prefix=cfg.id_prefix) and fill QaContext.git_sha from git_sha(); data_vintage keys starting with 'lidar' are treated as LiDAR vintages
- 2026-11-22 [integrator] integrator note from SCAN-006: look up building licence/attribution notices from SOURCE_NOTICES by the frame's 'source' column (frame.attrs may not survive pandas ops)
