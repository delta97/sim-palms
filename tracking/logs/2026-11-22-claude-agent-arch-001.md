# Session log: 2026-11-22, claude-agent, arch-001

- **Started / ended:** 2026-11-22 (single session)
- **Agent / model / person:** claude-agent
- **Branch / worktree:** task/arch-001-scaffold-the-python-monorepo-pyproject-p, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ARCH-001
- **Tasks:** ARCH-001 (in_progress -> review)

## Goal

Scaffold the palmfix Python project: pyproject, package roots, error hierarchy, schema loader, tests, CI workflow.

## What changed

- `pyproject.toml`: hatchling build, deps/extras, scripts, ruff/mypy/pytest config (92514ec)
- `palmcore/{__init__,errors,schemas}.py`, `palmcore/py.typed`, `palmscan/__init__.py`, `palmgen/__init__.py` (92514ec)
- `tests/unit/palmcore/test_package.py`, `test_schemas_loader.py` (92514ec)
- `.github/workflows/python.yml`: lint + test (ubuntu, windows) (92514ec)
- `schemas/.gitkeep`: lets the wheel force-include resolve until ARCH-002 adds schemas (92514ec, touches updated in 308a93d)

## Verification

Local venv on Python 3.14.2: ruff check and format --check clean, mypy clean (5 files), pytest 23 passed, coverage 97.3%, versions print 0.1.0 x3.

## Decisions and findings

- WS1 regex `^[a-z0-9-]+\.schema\.json$` rejects `palms.geojson.schema.json`; the check is applied only to names outside SCHEMA_FILES.
- Ruff 0.17 also formats Markdown code blocks; pyproject excludes `*.md` from format and `scripts/` from ruff.
- Hatch force-include fails if `schemas/` is missing, hence `schemas/.gitkeep`.

## Open issues

- Python 3.12 install and CI (ubuntu + windows) not verified; branch not pushed.
- VERIFY Q4 (extras on windows-latest) unconfirmed.
- scripts/tasks.py has pre-existing ruff errors (excluded, not fixed).

## Handoff: next steps

1. Integrator: push the branch, check `python / lint` and both `python / test` jobs, then tick the remaining acceptance boxes and merge.
2. ARCH-002: add schemas under `schemas/` (keep or delete `.gitkeep`).
