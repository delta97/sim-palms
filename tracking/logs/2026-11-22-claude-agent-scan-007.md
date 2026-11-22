# Session log: 2026-11-22, claude-agent, scan-007 recorded fixtures

- **Started / ended:** 2026-11-22
- **Agent / model / person:** claude-agent
- **Branch / worktree:** task/scan-007-record-live-source-fixtures-and-confirm, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-007
- **Tasks:** SCAN-007 (in_progress -> review)

## Goal

Record small real responses from each Phase 1 source with the merged adapters, answer the source-field questions, and extend the species and status tables with observed values.

## What changed

- `tests/fixtures/palmscan/recorded/`: four source folders plus a README with URLs, dates, bboxes, licences and answers.
- `tests/unit/palmscan/test_scan_recorded_sources.py`: offline replay of every fixture, table cases.
- `palmscan/data/species_aliases.csv`, `non_tree_markers.yaml`, `palmscan/filters.py`: new aliases, whole-string status codes (`RM`).
- `regions/san-diego-coastal.yaml`, `regions/la-westside.yaml`: `status_field: MAPNG_STAT_CD`, corrected comments.
- `plans/detailed/02-detection-pipeline.md` W5: implementation note.

## Verification

pytest 1548 passed, 4 skipped; ruff, ruff format, mypy clean.

## Decisions and findings

See the fixtures README. Main finding: San Diego removed rows (25% of the layer) were not filtered without a status field.

## Open issues

- Hyophorbe (bottle palm) has no registry key or size default; mapped to `palm_unknown`.
- Real 627 MB county file not read; memory is extrapolated from a 289 MB synthetic file.
- StreetsLA WFS and Microsoft tile download not built.

## Handoff: next steps

1. SCAN-100 live run: re-check `MAPNG_STAT_CD` handling in QA counts; consider a Santa Monica per-city source for LA.
