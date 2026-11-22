# Session log: 2026-11-22, integrator, orchestration of the first build wave

- **Started / ended:** 2026-11-22 (one long session)
- **Agent / model / person:** integrator session orchestrating specialist subagents, one per task, each in its own worktree
- **Branch / worktree:** `main` (primary checkout); task branches `task/<id>-<slug>` in `../sim-palms-worktrees/<ID>`
- **Tasks:** 55 tasks todo -> done (see CHANGELOG.md); SCAN-020, SCAN-024, SCAN-025, SCAN-027 in progress at the time of writing

## Goal

Clone the repo, work the GitHub issues in order, use parallel worktrees and subagents, and keep `main`, the issues and the tracking files in step.

## What changed

- 55 task branches merged with `--no-ff` (merge commits carry `Task:` trailers). Each task: tests/lint/types green, task set `done`, one CHANGELOG line, board regenerated, pushed, issue closed with the merge-commit link.
- `.gitattributes`: forces LF in working trees (the machine has `core.autocrlf=true` system-wide, which broke byte-for-byte golden comparisons).
- `scripts/tasks.py`: writes task files and the board with LF.
- Integrator fixes on `main`: `palmcore/config.py` logger under the `palmfix` root (ARCH-003); `placement.scale_clamp` made an optional override with no default, per ASSET-005 (found by GEN-004); plan 04 GUID table aligned with plan 01 WS4 (GEN-002); task texts aligned with plans where the plan was authoritative (ARCH-004 cache_key, ARCH-006 `loc:` prefix); RISK-005 watch docs pointed at the TEST-015 regression routine.

## Verification

- Full suite on `main` after the last merge: 1684 passed, 5 skipped (skips: rasterio-only tests, and the local-palmscan-output contract test). `ruff check`, `ruff format --check`, `mypy`: clean.
- GitHub Actions `python.yml` green on Ubuntu and Windows for pushed `main` commits that were not superseded.
- `python scripts/tasks.py validate`: 213 tasks, 0 errors.

## Decisions and findings

- Proceeded with Linux code into Phases 1-4 before Phase 0 per the **proposed** ADR-0013. If the user rejects it, nothing needs reverting; later code simply waits for the gates.
- Where a task text and its plan section disagreed, the plan won and the task text was fixed (logged in each task).
- The asset manifest owns scale limits and species fallback; regions may override (ASSET-005, GEN-011, ARCH-003 follow-up).
- Real-data facts from SCAN-007 (San Diego `MAPNG_STAT_CD` removed-tree status, null `SPECIES_NAME`, pagination; la-trees ids are row indices) are in the plan W5 and the recorded-fixture README.

## Open issues

See "Known gaps" in `tracking/STATUS.md`. ASSET-001 merged with one acceptance box open (about six proportions with no published source; to be measured from photos in ASSET-010 and the model tasks).

## Handoff: next steps

1. Integrate SCAN-020/024/025/027 as they reach `review`, then claim SCAN-028 (`python scripts/tasks.py batch --requires none,network`).
2. User: DEC-004, then SPIKE-001 on the sim PC; review ADR-0001 and ADR-0013.
3. Remaining agent-ready work after the LiDAR batch: TEST-013, TEST-008, FX-002 (later phases).
