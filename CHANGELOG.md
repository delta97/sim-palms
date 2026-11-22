# Changelog

One line per merged task, newest first, written at merge time on `main` (see AGENTS.md section 4).
Format: `- TASK-ID: what changed (PR link)`.

## Unreleased

- FX-009: Added calibration (vfov, time offset, pose bias, depth model) from clicks, the click store and UI, and `palmfx calib`/`palmfx clicks`; click UI not yet run on a display (local merge).
- FX-010: Added palm masks by projecting palms.geojson through the camera model, with depth-buffer occlusion (`palmfx mask-project`) (local merge).
- FX-004: Added the synthetic test scene generator and session fixtures for palmfx (`palmfx/offline/synth.py`) (local merge).
- FX-008: Added capture-session ingest, circular-heading pose interpolation and the sample-fixture builder (`palmfx ingest`, `palmfx fixture`); capture formats are VERIFY (local merge).
- FX-014 (partial, task blocked): Added the inpainting runner with the Telea baseline and tiling (tested) and the LaMa backend (untested: needs torch and the weights; checksum pending in `models.lock.json`) (local merge).
- FX-012: Added mask comparison metrics (pixel IoU, instance precision/recall) and the `palmfx mask-compare` command (local merge).
- FX-003: Added the camera model (WGS84 to ENU geodesy, attitude, pinhole projection and back-projection); sim conventions are VERIFY (local merge).
- FX-005: Added the log24 ReShade depth-pack shader (untested in ReShade) and its Python depth decoder and depth-model fit (local merge).
- TEST-014: Added soak-test checks S1-S6, provisional limits and the SOAK procedure for the live spawner (`tests/perf/soak.py`) (local merge).
- FX-002: Scaffolded the `palmfx.offline` package (session I/O, pluggable command CLI, `fx` extra) for the Phase 7 Stage A experiment (local merge).
- SCAN-028: Wired the LiDAR stages (EPT tiles, CHM, crowns, rules, merge, classifier) into `palmscan run`, QA outputs and `palmscan eval`; real PDAL/3DEP untested (local merge).
- Repo: disabled the GitHub Actions workflows (`python`, `tracking`) at the user's request; added `scripts/ci.py`, a local CI that runs the same lint, type, test/coverage and tracking checks.
- TEST-013: Added the frametime capture parser and run comparison report (`tests/perf/`), budget provisional until DEC-005 (local merge).
- TEST-008: Added optional image-diff scoring for visual viewpoints (`tests/visual/diff_score.py`), thresholds uncalibrated until TEST-018 (local merge).
- SCAN-020: Added the 3DEP EPT LiDAR adapter (pipeline generation, tiling, streamed tile cache, injectable PDAL runner); PDAL round-trip untested locally (local merge).
- SCAN-027: Added the decision-tree species classifier (JSON model, used only when it beats the rules in CV) (local merge).
- SCAN-025: Added deterministic inventory-to-LiDAR matching and merge with LiDAR-only palm keys (local merge).
- SCAN-024: Added the LiDAR palm rule filter with reject reasons feeding qa_rejects.csv (local merge).
- SCAN-007: Recorded small live fixtures from San Diego, OSM and la-trees; found the San Diego status field (25% removed trees), null species names and source format facts (local merge).
- ASSET-001: Added reference sheets for the five SoCal palm species (`assets/reference/`), with cited proportions and licensed photo links (local merge).
- SCAN-029: Added in-run accuracy evaluation from palmscan QA, calling the TEST-010 metrics (local merge).
- SCAN-023: Added CHM peak detection and watershed crown segmentation (`palmscan/detect/peaks.py`) (local merge).
- SCAN-013: Added the `palmscan run` pipeline and `run`/`priors` CLI, end to end on offline fixtures with contract-valid, byte-reproducible output (local merge).
- SCAN-026: Added species shape rules and the four-step classification order (`palmscan/classify/species.py`) (local merge).
- TEST-010: Added the accuracy metrics script with configurable thresholds (`tests/accuracy/metrics.py`), the single implementation SCAN-029 will call (local merge).
- SCAN-022: Added the canopy height model (DTM, DSM, CHM) on numpy, with fast deterministic gap filling (local merge).
- SCAN-008: Added the inventory ingest stage (adapter registry, cache freshness) and deterministic cross-source dedupe (local merge).
- SCAN-006: Added the building footprints adapter (OSM multipolygons, Microsoft file) producing contract-valid buildings (local merge).
- SCAN-009: Added palm sizes, exclusion radius, building conflicts and mask_out handling (`palmscan/attributes.py`, `palmscan/mask.py`) (local merge).
- TEST-009: Added the ground-truth schema, `gt` CLI and labeling guide (labels themselves are user work in TEST-101/TEST-011) (local merge).
- TEST-102: Added the visual test protocol, run scaffolder, run checker, checklist template and test log (`tests/visual/`) (local merge).
- SCAN-004: Added the ArcGIS REST inventory adapter with paging, object-id fallback and cache (local merge).
- SCAN-005: Added the cached, tiling Overpass client and the OSM tree adapter with ODbL attribution (local merge).
- SCAN-012: Added palmscan QA outputs: qa_summary.md, qa_map.gpkg and qa_rejects.csv (local merge).
- SCAN-002: Added the species key registry (63 keys), alias table (220 rows), normalizer and palm filter (local merge).
- SCAN-003: Added the source adapter base and the geojson_file adapter (bbox-filtered reads, CRS handling, CSV streaming) (local merge).
- TEST-017: Added the test runbook and CI wiring notes (`tests/README.md`), verified on Windows and Ubuntu/Python 3.12 (local merge).
- SCAN-010: Added species priors from inventory mixes and deterministic prior sampling (`palmscan/classify/priors.py`) (local merge).
- SCAN-011: Added the palmscan palms.geojson writer, stable palm ids and contract validation (`palmscan/output.py`) (local merge).
- GEN-007: Added mod and airport masks (buffered in local CRS) and the Overpass airport fetch (`palmgen masks airports`) (local merge).
- ASSET-002: Collected build-vs-license inputs for DEC-002 (`assets/reference/build-vs-license.md`) (local merge).
- SCAN-001: Added the palmscan package core: config, cache, HTTP client with retries and User-Agent, models, CLI skeleton (local merge).
- GEN-011: Added variant selection, scaling and heading (`palmgen/variants.py`) with manifest-owned scale limits and species fallback; aligned plan 04 (local merge).
- TEST-015: Added the post-update regression routine (`tests/regression/ROUTINE.md`), its log and the entry scaffolder (local merge).
- ASSET-006: Added glTF stats, automated asset checks, triangle/height budgets (`assets/budgets.yaml`) and the `palmcore.assets check` CLI (local merge).
- GEN-004: Added palmgen input loading (palms, buildings, region config) and `GenConfig` satisfying the geometry RadiusConfig protocol (local merge).
- GEN-006: Added building-footprint clipping of exclusion clusters (`clip_buildings`, hole removal) (local merge).
- ARCH-009: Added shared CLI plumbing (`run_main`, context, exit codes) and the `palmfix` utility CLI (validate, regions, config) (local merge).
- TEST-003: Added geometry assertion helpers for exclusion polygons (`tests/helpers/geom.py`) (local merge).
- GEN-008: Added the template engine and deterministic XML writer, tested on fake templates (real templates come from SPIKE-003) (local merge).
- GEN-005: Added exclusion geometry (palm circles, cluster merge, simplification, ring normalisation); fixed the plan's 3 m row merge example (local merge).
- GEN-014: Added build_report.json and build_report.md generation for palmgen (local merge).
- TEST-004: Added palms.geojson contract conformance tests, invariant checks and a validator CLI (`tests/helpers/contract.py`) (local merge).
- TEST-002: Added the golden-file comparison helper with `--update-golden` (refused under CI) (local merge).
- ARCH-007: Added the palms.geojson serializer, reader and writer (`palmcore/palms.py`), deterministic LF output (local merge).
- ARCH-008: Added the San Diego coastal and LA Westside example region configs with verified source endpoints (local merge).
- TEST-005: Added the test-site registry schema and loader with a placeholder T1-T5 skeleton (local merge).
- GEN-003: Added 0.01 degree tiling and canonical tile naming for palmgen (local merge).
- GEN-002: Added deterministic GUIDs and per-palm hashes for palmgen, wrapping palmcore ids; aligned plan 04 with plan 01 (local merge).
- ASSET-005: Added the asset manifest schema, species spec format, loader and generator (`palmcore.assets`) (local merge).
- Repo: added `.gitattributes` forcing LF in working trees so golden files match across Windows and Linux.
- ARCH-002: Added the palms.geojson and buildings.geojson JSON Schemas and the shared validator (`palmcore/contract.py`) (local merge).
- ARCH-003: Added the region YAML config schema and loader (`palmcore/config.py`) (local merge).
- SPIKE-009: Added the SimConnect spawn-and-disconnect spike console app (`spikes/simconnect-persist/`) for SPIKE-005 on the sim PC (local merge).
- GEN-001: Scaffolded the palmgen package, CLI surface, error types and data model (local merge).
- RISK-002: Audited palm model, texture and tool licenses (`docs/licenses/models-and-tools.md`), with 10 open questions (local merge).
- TEST-001: Added the shared pytest harness (run flags, network guard, path fixtures) and fixture loaders (local merge).
- RISK-004: Added `docs/compat/airports-mask.geojson` (60 SoCal airport boundaries from OSM) and `docs/compat/airports.md` with known add-ons (local merge).
- ARCH-004: Added palmcore logging setup, repo path resolution and the download-cache helpers (local merge).
- ARCH-005: Added palmcore geo helpers (Bbox, haversine, UTM/local CRS, transforms); corrected the WS3 haversine test value (local merge).
- ARCH-006: Added deterministic UUIDv5 palm ids, object GUIDs and seeded randomness to palmcore (local merge).
- RISK-001: Audited data source licenses and terms (`docs/licenses/data-sources.md`), with 10 open questions for the user (local merge).
- ARCH-001: Scaffolded the `palmfix` Python project (pyproject, palmcore/palmscan/palmgen roots, errors, schema locator, ruff/mypy/pytest, CI workflow) (local merge).
- RISK-005: Added the sim/SDK update watch process (`docs/process/sim-update-watch.md`) and its log with the first exclusion-bug pass (local merge).
- INFRA-001: Added the original plan set, detailed per-plan breakdowns with task files, file-based task tracking
  (`scripts/tasks.py`), worktree helper (`scripts/wt.sh`), operating protocol (`AGENTS.md`), specialist agents and skills
  ([delta97/sim-palms#1](https://github.com/delta97/sim-palms/pull/1)).
