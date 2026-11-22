# Changelog

One line per merged task, newest first, written at merge time on `main` (see AGENTS.md section 4).
Format: `- TASK-ID: what changed (PR link)`.

## Unreleased

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
