---
id: ARCH-009
title: "Add shared CLI plumbing and the palmfix utility CLI"
status: todo
phase: 1
area: ARCH
kind: build
plan_ref: plans/detailed/01-architecture.md#ws9-shared-cli-plumbing-and-palmfix
depends_on: [ARCH-003, ARCH-004, ARCH-007]
requires: [none]
agent: python-architect
estimate_h: 4
touches: [pyproject.toml, palmcore/context.py, palmcore/cli_common.py, palmcore/cli.py, palmcore/__main__.py, tests/unit/palmcore/test_cli_common.py, tests/unit/palmcore/test_cli.py]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Two pieces:
- Shared CLI plumbing (`RunContext`, common flags, region loading, logging setup, exception-to-exit-code mapping). The `palmscan` and `palmgen` CLIs can reuse it so all tools behave the same.
- A complete `palmfix` utility CLI with `validate`, `regions` and `config`, for checking contract files and region configs from the shell.

## Context

- `RunContext`, `cli_common` signatures, `palmfix` output formats and exit codes: plan_ref section WS9. Default exit codes: `palmcore/errors.py` (ARCH-001; WS1 in the same plan).
- `palmscan/cli.py` and `palmgen/cli.py` are **not** part of this task. SCAN-001 and GEN-001 own them (open question Q5). Don't create or edit anything under `palmscan/` or `palmgen/`.
- GEN uses its own exit codes. `run_main` therefore takes an `error_map` so GEN can reuse it without adopting the `palmcore` numbers.
- Uses `palmcore.config` (ARCH-003), `palmcore.paths` and `palmcore.log` (ARCH-004), and `palmcore.contract` and `palmcore.palms` (ARCH-002, ARCH-007).
- The only `pyproject.toml` change is adding `palmfix = "palmcore.cli:main"` to `[project.scripts]`.

## Steps

1. `palmcore/context.py`: the frozen `RunContext` with the `log` property and `require_region()`.
2. `palmcore/cli_common.py`:
   - `add_common_args` (`-v` count and `-q` in a mutually exclusive group, `--data-dir`, `--build-dir`, `--regions-dir`, `--log-file`, `--no-log-file`);
   - `add_region_arg`, `build_paths`, `build_context`;
   - `run_main(parser, argv, *, error_map=None)`. It checks `error_map` first (most specific class in the MRO wins), then `PalmfixError.exit_code`, `KeyboardInterrupt` → 130, any other exception → traceback logged and 1; no subcommand → help printed and 2.
3. `palmcore/cli.py`: `build_parser()` and `main(argv=None) -> int` with subcommands `validate PATH [--region R] [--strict] [--json]`, `regions [--check]` and `config --region R [--format yaml|json]`. Each subcommand gets the common args and sets `func` via `set_defaults`. Output formats exactly as in WS9; `validate` prints at most 50 issues, then `... and N more`.
4. `palmcore/__main__.py`: `from palmcore.cli import main; raise SystemExit(main())`.
5. Add `palmfix = "palmcore.cli:main"` to `[project.scripts]` in `pyproject.toml`, then reinstall with `pip install -e ".[dev]"`.
6. `tests/unit/palmcore/test_cli_common.py`:
   - flags beat env vars;
   - `-v -q` exits 2;
   - `run_main` maps `ConfigError` → 2, `ContractError` → 3, `CacheMiss` → 5, `KeyboardInterrupt` → 130, `RuntimeError` → 1;
   - an `error_map={ContractError: 7}` overrides the default;
   - no subcommand prints help and returns 2;
   - a log file appears under `<build-dir>/logs/` unless `--no-log-file`;
   - `RunContext.require_region()` raises `ConfigError` when the region is None.
7. `tests/unit/palmcore/test_cli.py`: call `main([...])` with `--build-dir tmp_path`, using `capsys`:
   - `validate` on `tests/fixtures/palmcore/palms_io/sample_10.geojson` exits 0 and prints `OK: 10 features`;
   - `validate` on `palms/invalid/duplicate_palm_id.geojson` exits 3 and prints `error features[`;
   - `--json` stdout parses as JSON;
   - `palms/valid_empty.geojson` exits 0, and 3 with `--strict`;
   - `regions --regions-dir tests/fixtures/palmcore/regions` lists `full` and `minimal`;
   - `regions --check` on `dup_prefix/` exits 2;
   - `config --region minimal --regions-dir ... --format json` parses and includes `exclusion.margin_m == 1.5`;
   - an unknown region exits 2.
8. Smoke-test the installed script and the `python -m` form (Verification).

## Acceptance criteria

- [ ] `palmfix --help` and `python -m palmcore --help` work after `pip install -e .`.
- [ ] Each exit code in WS1/WS9 is proven by a test, including the `error_map` override.
- [ ] Results go to stdout and logs to stderr. `validate --json` prints only JSON on stdout.
- [ ] No files under `palmscan/` or `palmgen/` change.
- [ ] ruff, mypy and pytest are green on Ubuntu and Windows CI.

## Verification

```bash
pip install -e ".[dev]"
palmfix --help && python -m palmcore --help >/dev/null
palmfix validate tests/fixtures/palmcore/palms_io/sample_10.geojson --no-log-file; echo "exit=$?"     # OK: 10 features ... exit=0
palmfix validate tests/fixtures/palmcore/palms/invalid/duplicate_palm_id.geojson --no-log-file; echo "exit=$?"   # exit=3
palmfix regions --regions-dir tests/fixtures/palmcore/regions --no-log-file
palmfix config --region minimal --regions-dir tests/fixtures/palmcore/regions --format json --no-log-file
pytest tests/unit/palmcore/test_cli_common.py tests/unit/palmcore/test_cli.py -q
ruff check . && mypy
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
