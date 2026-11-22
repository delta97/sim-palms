---
id: ARCH-001
title: "Scaffold the Python monorepo (pyproject, package layout, lint/test tooling, CI)"
status: todo
phase: 1
area: ARCH
kind: build
plan_ref: plans/detailed/01-architecture.md#ws1-tooling-and-ci
depends_on: [GATE-P0]
requires: [none]
agent: python-architect
estimate_h: 4
touches: [pyproject.toml, palmcore/__init__.py, palmcore/py.typed, palmcore/errors.py, palmcore/schemas.py, palmscan/__init__.py, palmgen/__init__.py, .github/workflows/python.yml, tests/unit/palmcore/test_package.py, tests/unit/palmcore/test_schemas_loader.py]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

A single installable Python project (`palmfix`) with the three package roots, ruff/mypy/pytest configuration, console-script entry points, the shared error hierarchy, a schema-file locator, and a GitHub Actions workflow that lints and tests on Ubuntu and Windows. Every later Python task in every area builds on this.

## Context

- The repo root is the `palmfix/` of `plans/01-architecture.md`. Do not create a nested `palmfix/` directory.
- Exact values (dependency groups, ruff/mypy/pytest settings, exit codes, schema lookup order, CI jobs) are in the plan_ref section WS1. The dependency list already merges what SCAN, GEN and TEST asked for in `plans/detailed/02-detection-pipeline.md`, `plans/detailed/04-fs2024-integration.md` and `plans/detailed/06-testing.md`. Don't add tools beyond WS1 (no pre-commit, no lockfile).
- Declare `palmscan = "palmscan.cli:main"` and `palmgen = "palmgen.cli:main"` now, even though those modules don't exist yet. SCAN-001 and GEN-001 write them, and this way they never have to edit `pyproject.toml`. ARCH-009 adds `palmfix` later.
- `palmscan/__init__.py` and `palmgen/__init__.py` hold only a docstring and `__version__ = "0.1.0"`. SCAN and GEN own them afterwards.
- Do NOT edit `.gitignore` (bootstrap owns it). If `data/`, `build/` and the tool caches are not ignored yet, note it in the Log.
- Do NOT create `tests/conftest.py`, `tests/__init__.py` or `tests/helpers/` (TEST-001 owns them). With `--import-mode=importlib` and `pythonpath = ["."]`, ARCH tests work without them.
- The schema JSON files don't exist yet (ARCH-002, ARCH-003). Test `schemas.py` with a temporary directory via `PALMFIX_SCHEMA_DIR`.
- Depends on GATE-P0 because plan 05 says nothing is built before Phase 0 passes.

## Steps

1. Create `pyproject.toml`: hatchling backend; `name = "palmfix"`, `version = "0.1.0"`, `requires-python = ">=3.12"`; base deps and extras `dev`, `scan`, `lidar`, `pdal`, `gen` exactly as in the WS1 table; `[tool.hatch.build.targets.wheel] packages = ["palmcore", "palmscan", "palmgen"]` and the `force-include` of `schemas` → `palmcore/_schemas`; `[project.scripts]` with `palmscan` and `palmgen`.
2. Add `[tool.ruff]`, `[tool.ruff.lint]`, `[tool.mypy]` with its two overrides, and `[tool.pytest.ini_options]` (testpaths, `pythonpath = ["."]`, addopts list, markers `network`, `sim`, `slow`) as in WS1.
3. Create `palmcore/__init__.py`, `palmscan/__init__.py`, `palmgen/__init__.py` (docstring + `__version__ = "0.1.0"`), and an empty `palmcore/py.typed`.
4. Create `palmcore/errors.py`: the `EXIT_*` constants and the classes `PalmfixError`, `ConfigError`, `ContractError` (stores `issues`), `SourceError`, `CacheMiss(SourceError)`, `ExternalToolError`, each with its `exit_code` class attribute.
5. Create `palmcore/schemas.py`: `SCHEMA_FILES`, `schema_dir()`, `load_schema(name)` (accepts a `SCHEMA_FILES` key or any file name matching `^[a-z0-9-]+\.schema\.json$`, so ASSET-005 can load `asset-manifest.schema.json` without editing this module; other names raise `ValueError`; `functools.cache`; `PalmfixError` naming the full path when the file is missing or isn't valid JSON), and `make_validator(schema)` (runs `Draft202012Validator.check_schema` first, then builds the validator with `FORMAT_CHECKER`).
6. Write `tests/unit/palmcore/test_package.py`: all three packages import; each `__version__` is `"0.1.0"`; every exception subclasses `PalmfixError` and has the documented exit code; `CacheMiss` is a `SourceError`.
7. Write `tests/unit/palmcore/test_schemas_loader.py`: with `monkeypatch.setenv("PALMFIX_SCHEMA_DIR", str(tmp_path))` and a tiny schema file, `load_schema("palms")` and `load_schema("extra.schema.json")` both return their file (call `load_schema.cache_clear()` in a fixture); `load_schema("../x")` raises `ValueError`; a missing file raises `PalmfixError` mentioning the path; a nonexistent `PALMFIX_SCHEMA_DIR` raises `ConfigError`; `make_validator({"type": 5})` raises.
8. Create `.github/workflows/python.yml` with the `lint` and `test` jobs, triggers, path filters and concurrency group from WS1.
9. Run the Verification commands in a fresh venv. Push the branch and confirm all CI jobs pass on Ubuntu and Windows. If any extra fails to install on `windows-latest`, record it in the Log under `VERIFY Q4` and give the failing package.

## Acceptance criteria

- [ ] `pip install -e ".[dev,scan,lidar,gen]"` succeeds on Python 3.12 (Linux locally, Windows in CI).
- [ ] `ruff check .`, `ruff format --check .` and `mypy` report no errors.
- [ ] `pytest` passes locally and in CI.
- [ ] The `python` workflow is green on `ubuntu-latest` and `windows-latest` for this branch.
- [ ] `[project.scripts]` lists `palmscan` and `palmgen` only.
- [ ] The diff contains no `conftest.py`, no `tests/__init__.py`, no `.gitignore` edits, no `palmscan/cli.py` or `palmgen/cli.py`.

## Verification

```bash
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev,scan,lidar,gen]"
ruff check . && ruff format --check . && mypy
pytest -q -m "not network and not sim" --cov=palmcore --cov-fail-under=85
python -c "import palmcore, palmscan, palmgen; print(palmcore.__version__, palmscan.__version__, palmgen.__version__)"   # 0.1.0 0.1.0 0.1.0
```

Then open the PR's Checks tab: `python / lint` and both `python / test` matrix jobs are green.

## Log

- 2026-11-21 [plan-breakdown] Task created.
