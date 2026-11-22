# Changelog

One line per merged task, newest first, written at merge time on `main` (see AGENTS.md section 4).
Format: `- TASK-ID: what changed (PR link)`.

## Unreleased

- RISK-001: Audited data source licenses and terms (`docs/licenses/data-sources.md`), with 10 open questions for the user (local merge).
- ARCH-001: Scaffolded the `palmfix` Python project (pyproject, palmcore/palmscan/palmgen roots, errors, schema locator, ruff/mypy/pytest, CI workflow) (local merge).
- RISK-005: Added the sim/SDK update watch process (`docs/process/sim-update-watch.md`) and its log with the first exclusion-bug pass (local merge).
- INFRA-001: Added the original plan set, detailed per-plan breakdowns with task files, file-based task tracking
  (`scripts/tasks.py`), worktree helper (`scripts/wt.sh`), operating protocol (`AGENTS.md`), specialist agents and skills
  ([delta97/sim-palms#1](https://github.com/delta97/sim-palms/pull/1)).
