# Changelog

One line per merged task, newest first, written at merge time on `main` (see AGENTS.md section 4).
Format: `- TASK-ID: what changed (PR link)`.

## Unreleased

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
