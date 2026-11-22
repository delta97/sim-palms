---
id: TEST-001
title: Build the shared pytest harness and fixture loaders
status: review
phase: 1
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#unit-harness"
depends_on: [ARCH-001]
requires: [none]
agent: test-engineer
estimate_h: 3
touches: [tests/__init__.py, tests/conftest.py, tests/helpers/__init__.py, tests/helpers/fixtures.py, tests/unit/helpers/test_fixtures.py, tests/unit/helpers/test_conftest.py, tests/fixtures/helpers/]
owner: claude-agent
branch: task/test-001-build-the-shared-pytest-harness-and-fixt
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-001"
updated: 2026-11-22
---

## Goal

`tests/conftest.py` and `tests/helpers/fixtures.py` exist, so every area can write unit tests with shared markers, a network guard and fixture loaders. Every later TEST task builds on this.

## Context

- Spec: `plans/detailed/06-testing.md` sections "Pytest markers and flags", "Helper API" (fixtures.py part) and "Unit harness".
- Pytest config lives in `pyproject.toml` (ARCH-001). This task does not edit it. Check that ARCH-001 set `pythonpath = ["."]`, `--import-mode=importlib` and `testpaths = ["tests"]` (see "Pytest configuration requested from ARCH-001"). `plans/detailed/01-architecture.md` also plans pytest-socket `--disable-socket` with `@pytest.mark.enable_socket` for network tests. If not, log it on ARCH-001 with `python3 scripts/tasks.py log ARCH-001 "..."` and work around it locally with `PYTHONPATH=.`.
- `tests/__init__.py` makes `tests` a package so later tools run as `python -m tests.<layer>.<tool>`.

## Steps

1. Create `tests/__init__.py` and `tests/helpers/__init__.py` (empty, one docstring line each).
2. `tests/helpers/fixtures.py`: `REPO_ROOT` (found by walking up to `pyproject.toml`), `FIXTURES_ROOT`, and the functions `fixture_path`, `load_text`, `load_bytes`, `load_json`, `load_yaml`, `load_geojson`, `copy_fixture_tree` with the exact signatures in the plan. `fixture_path` raises `FileNotFoundError` naming the full expected path and listing up to 10 files that do exist in that package dir.
3. `tests/conftest.py`:
   - `pytest_addoption`: `--run-network`, `--run-sim` (store_true).
   - `pytest_configure`: register markers `network`, `sim`, `slow` with `config.addinivalue_line("markers", ...)`.
   - `pytest_collection_modifyitems`: skip `network` items unless `--run-network`; skip `sim` items unless `--run-sim` and `sys.platform == "win32"`. Skip reasons say which flag to pass.
   - Network guard. If pytest-socket is active (ARCH-001's `--disable-socket`): in `pytest_collection_modifyitems`, add `pytest.mark.enable_socket` to every item marked `network`, so authors only write `@pytest.mark.network`. If pytest-socket is not installed or not enabled: autouse fixture `_network_guard` that, unless the test has the `network` marker, monkeypatches `socket.socket.connect` and `connect_ex` so AF_INET/AF_INET6 connects to non-loopback addresses raise `RuntimeError("network disabled in tests: use tests/fixtures or mark @pytest.mark.network")`. Detect which case applies with `config.pluginmanager.hasplugin("socket")` and the `--disable-socket` option value. Loopback and AF_UNIX stay allowed.
   - Fixtures `repo_root`, `fixtures_root`, `golden_root` (returns `REPO_ROOT / "tests" / "golden"`; the golden helper itself is TEST-002).
4. Fixtures for self-tests: `tests/fixtures/helpers/sample.json`, `sample.yaml`, `sample.geojson` (one Point feature), `tree/a.txt`, `tree/sub/b.txt`.
5. `tests/unit/helpers/test_fixtures.py`: each loader on the samples; missing-file error message contains the path; `load_geojson` rejects a non-GeoJSON JSON; `copy_fixture_tree` copies the nested tree into `tmp_path`.
6. `tests/unit/helpers/test_conftest.py` using the `pytester` plugin (enable with `pytest_plugins = ["pytester"]` in the test module): a `network`-marked test is skipped without the flag and runs with it; a `sim` test is skipped on Linux even with `--run-sim`; an unmarked test that connects to `203.0.113.1:80` is blocked (pytest-socket's error or the guard's RuntimeError, whichever is active); a `network`-marked test with `--run-network` is not blocked by the guard (use a monkeypatched socket so no real traffic is sent).

## Acceptance criteria

- [x] `pytest tests/unit/helpers -q` passes on Linux with no network access.
- [x] `pytest --markers` lists `network`, `sim`, `slow`.
- [x] An unmarked test opening a socket to a public IP is blocked; `@pytest.mark.network` alone (no `enable_socket`) is enough to allow it under `--run-network`.
- [x] Loader signatures match `plans/detailed/06-testing.md#helper-api` exactly.
- [x] No edits to `pyproject.toml`.

## Verification

```bash
pytest tests/unit/helpers -q
pytest --markers | grep -E "network|sim|slow"
python -c "from tests.helpers.fixtures import load_json; print(load_json('helpers', 'sample.json'))"
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/test-001-build-the-shared-pytest-harness-and-fixt worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-001
- 2026-11-22 [claude-agent] Acceptance met (7a01e1d): pytest tests/unit/helpers 13 passed; full suite 85 passed; --markers lists network/sim/slow; unmarked connect to 203.0.113.1 blocked, @network + --run-network allowed (pytester); loader signatures match plan; pyproject.toml untouched. ruff check/format and mypy clean. ARCH-001 set pythonpath, importlib, testpaths but not pytest-socket, so the fallback socket guard is the active path (pytest-socket branch implemented, untested).
- 2026-11-22 [claude-agent] Status in_progress -> review.
