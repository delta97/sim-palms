---
id: ARCH-004
title: "Add palmcore logging, path resolution and download-cache helpers"
status: todo
phase: 1
area: ARCH
kind: build
plan_ref: plans/detailed/01-architecture.md#ws2-errors-logging-paths-and-cache
depends_on: [ARCH-001]
requires: [none]
agent: python-architect
estimate_h: 3
touches: [palmcore/log.py, palmcore/paths.py, palmcore/cache.py, tests/unit/palmcore/test_log.py, tests/unit/palmcore/test_paths.py, tests/unit/palmcore/test_cache.py]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Three small `palmcore` modules every tool uses:
- `log.py`: one logging setup for all tools.
- `paths.py`: where `data/`, `build/` and `regions/` are, with CLI-flag and env overrides.
- `cache.py`: the on-disk download-cache layout, provenance sidecars and atomic writes, which SCAN's `Cache` class builds on.

## Context

- Signatures, precedence rules, cache layout, sidecar keys and the atomic-write method: plan_ref section WS2.
- The cache layout `data/<namespace>/<key[:2]>/<key><suffix>` and the sha1 key match the SCAN plan (`plans/detailed/02-detection-pipeline.md`, W1 `palmscan/cache.py`). SCAN implements `get_or_fetch`, offline and refresh on top of these functions. This task downloads nothing.
- `CacheMiss` already exists in `palmcore/errors.py` (ARCH-001).
- Must work on Windows, where palmgen runs: use `pathlib` and `os.replace`, no POSIX-only calls. CI runs the tests on `windows-latest`.
- Tests use `tmp_path` only and never write into the repo's `data/` or `build/`.

## Steps

1. `palmcore/log.py`: `LOGGER_ROOT`, `get_logger`, `setup_logging(verbosity, *, log_file, stream)`, `new_run_id(now)`. Tag installed handlers with `_palmfix = True` and remove only those on a repeat call. The file handler is always DEBUG with UTC timestamps.
2. `palmcore/paths.py`: `REGION_RE`, the `Paths` dataclass with `resolve()` and the five path methods (`region_file`, `scan_out_dir`, `palms_path`, `package_project_dir`, `logs_dir`), and `ensure_dir()`. Repo-root detection looks for the line `name = "palmfix"` in `pyproject.toml`. A bad region name raises `palmcore.errors.ConfigError`.
3. `palmcore/cache.py`: `NAMESPACE_RE`, `canonical_json`, `cache_key`, `cache_path`, `meta_path`, `write_cache`, `read_meta`, `is_cached`, `is_fresh`, `atomic_write_bytes`, `atomic_write_text`. Write the data first and the meta second.
4. `tests/unit/palmcore/test_log.py`:
   - the verbosity → level mapping;
   - two `setup_logging` calls leave one palmfix stream handler;
   - at verbosity 0 the log file gets DEBUG lines while the stream gets INFO only;
   - `new_run_id(datetime(2026, 11, 21, 18, 4, tzinfo=UTC))` starts with `20261121T180400Z-` and ends with 6 hex characters.
5. `tests/unit/palmcore/test_paths.py`:
   - defaults under a fake repo in `tmp_path` (a `pyproject.toml` with `name = "palmfix"`; pass `cwd=` a subdirectory);
   - env overrides apply, and explicit arguments beat env;
   - relative env paths resolve against the repo root;
   - `palms_path("san-diego-coastal")` ends with `build/scan/san-diego-coastal/palms.geojson`;
   - `package_project_dir("san-diego-coastal")` ends with `build/palmfix-san-diego-coastal`;
   - `region_file("../x")` raises `ConfigError`.
6. `tests/unit/palmcore/test_cache.py`:
   - `cache_key` is the same for dicts with different insertion order and changes when a value changes;
   - `cache_key("abc")` equals the sha1 hex of `"abc"`'s canonical JSON;
   - `canonical_json` rejects NaN;
   - `cache_path(tmp, "lidar/ds_1", "ab12...", ".json")` gives `tmp/lidar/ds_1/ab/ab12....json`;
   - bad namespaces (`"../x"`, `"A B"`) and bad suffixes raise `ValueError`;
   - after `write_cache`, `is_cached` is True and `read_meta` has the six keys with the right sha256;
   - a data file without meta gives `is_cached == False`;
   - `is_fresh(p, None)` is True, and `is_fresh(p, 1, now=fetched + 2 days)` is False;
   - when `os.replace` is monkeypatched to raise, `atomic_write_bytes` leaves no `.tmp-*` file and keeps the old content.
7. Run the Verification commands.

## Acceptance criteria

- [ ] All names and signatures match WS2.
- [ ] Only `ensure_dir` (and the write functions in `cache.py`) create directories.
- [ ] Atomic writes leave no `.tmp-*` files, on success or failure.
- [ ] Tests pass on Linux locally and on Windows in CI.
- [ ] ruff, mypy (strict for palmcore) and pytest are green.

## Verification

```bash
pytest tests/unit/palmcore/test_log.py tests/unit/palmcore/test_paths.py tests/unit/palmcore/test_cache.py -q
python -c "from palmcore.paths import Paths; print(Paths.resolve().palms_path('san-diego-coastal'))"   # <repo>/build/scan/san-diego-coastal/palms.geojson
ruff check palmcore tests && mypy
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
