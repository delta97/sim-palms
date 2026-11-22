# Tests

How to run each test layer, what CI runs, what only runs on the sim PC, and how the CI wiring
is set up. Every command here was run on the branch base `38b886d`, with `.[dev,scan,lidar,gen,fx]` installed,
on Windows 11 (Python 3.14.2) and on Ubuntu 24.04 (Python 3.12.3, the CI version, under WSL). The
Ubuntu run is the closest local match to CI. The Windows CI job was not run locally. The files that CI, pytest and the CLIs depend on (`.github/`,
`pyproject.toml`, `tests/conftest.py`, `tests/helpers/`, `tests/regression/`, `scripts/`,
`.gitattributes`) are identical on main (`c4f5b50`). Main has since added palmscan and palmgen
tests, so the pass count on main will differ. Items marked **not built** name the task that
builds them.

Setup, from the repo root:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,scan,lidar,gen,fx]"   # Windows (Git Bash)
.venv/bin/python -m pip install -e ".[dev,scan,lidar,gen,fx]"       # Linux
```

Use the venv interpreter (or activate the venv) for every command below. The examples say
`python`. `python3` does not exist on the Windows dev box.

Do not install only `.[dev]`. `pip install -e ".[dev]"` alone fails to collect
`tests/unit/palmgen/test_templates.py` and `test_xml_writer.py` (no `jinja2`, which is in the
`gen` extra). CI installs all four extras.

## Layout

| Path | What it is | Status on main |
|---|---|---|
| `tests/conftest.py` | markers, run flags, network guard, shared fixtures | built (TEST-001) |
| `tests/helpers/fixtures.py` | fixture loaders (`load_json`, `copy_fixture_tree`, ...) | built (TEST-001) |
| `tests/helpers/golden.py` | golden-file comparison with an update flag | built (TEST-002) |
| `tests/helpers/geom.py` | geometry assertions | built (TEST-003) |
| `tests/helpers/contract.py` | `palms.geojson` schema plus invariants, CLI | built (TEST-004) |
| `tests/helpers/sites.py` | test-site registry loader | built (TEST-005) |
| `tests/helpers/build_checks.py` | build-output checks | **not built**, TEST-016 |
| `tests/sites/` | `sites.yaml` and schema; every site is `placeholder` | built, sites not defined; `<site>/flights/` **not built**, TEST-100 |
| `tests/unit/<package>/` | unit tests per area (`contract`, `helpers`, `palmcore`, `palmgen`, `palmscan`, `regression`) | built; area owners add their own |
| `tests/fixtures/<package>/` | recorded fixtures | built for `contract`, `helpers`, `palmcore`, `palmgen` |
| `tests/golden/<case>/` | golden output; GEN owns the cases | **not present**; created by GEN cases |
| `tests/accuracy/` | ground truth, thresholds, metrics | **not built**, TEST-009, TEST-010 |
| `tests/visual/` | visual protocol and run tools | **not built**, TEST-102 (diff scoring: TEST-008, optional) |
| `tests/perf/` | frametime parser, compare, soak | built: `frametimes`, `compare` (TEST-013), `soak` (TEST-014); flight harness TEST-103 (sim PC) |
| `tests/regression/` | post-update routine | `ROUTINE.md`, `LOG.md`, `new_entry.py` built (TEST-015); `check_build.py` and `build_history.csv` **not built**, TEST-016 |

## Run it

| Layer | Command | Runs in | Time |
|---|---|---|---|
| Unit, contract, helpers (the default gate) | `python -m pytest -m "not network and not sim"` | CI `python` workflow, `test` job, Ubuntu and Windows; locally | about 12 s on the dev box (760 passed, 1 skipped) |
| Coverage gate | `python -m pytest -m "not network and not sim" --cov=palmcore --cov-report=term-missing --cov-fail-under=85` | CI `test` job only | same run; palmcore was 95.3% |
| Lint | `python -m ruff check .` then `python -m ruff format --check .` | CI `lint` job (Ubuntu) | seconds |
| Types | `python -m mypy` | CI `lint` job (Ubuntu) | seconds |
| Slow tests | `python -m pytest -m "not slow"` skips them; `-m slow` runs only them | CI runs them (no deselect); locally optional | 1 test on main (`test_contract.py::test_ten_thousand_features_under_budget`) |
| Network | `python -m pytest --run-network -m network` | by hand, locally, **never CI** | **0 tests on main**; added by the owning task (e.g. TEST-012) |
| Sim | `python -m pytest --run-sim -m sim` | sim PC only (Windows, MSFS 2024, SDK); skipped on other OSes even with the flag | **0 tests on main**; added by owning tasks |
| Golden | `python -m pytest --update-golden`, then review the diff | locally only, refused under `CI` | no golden cases on main yet |
| Contract, one file | `palmfix validate PATH [--region NAME\|PATH] [--strict] [--json]` | anywhere; ARCH-009 | seconds |
| Contract, module CLI | `python -m tests.helpers.contract PATH [--region PATH]` | anywhere; TEST-004 | seconds |
| Regions | `palmfix regions`, `palmfix regions --check`, `palmfix config --region NAME [--format json]` | anywhere; ARCH-009 | seconds |
| Tracking | `python scripts/tasks.py validate` | CI `tracking` workflow (as `python3`, Ubuntu); locally | seconds |
| Regression routine | see `tests/regression/ROUTINE.md` | step 0 anyone; R1, R3 on the sim PC; R2 needs TEST-016 | 1 min to 60 min per step (estimate) |

Checked exit codes on main:

- `palmfix validate` on a valid file: 0. On `dup_palm_id.geojson`: 3 (contract error). Unknown flag: 2.
- `palmfix validate ... --region tests/fixtures/contract/region-minimal.yaml` on a valid file: 0.
- `palmfix config --region minimal`: 2. `regions/` holds only `la-westside` and `san-diego-coastal`.
  To use a region file in a test or a dry run, pass its path to `--region`.
- `python -m tests.helpers.contract` on a bad file: 1. On a good file: 0.
- `python -m tests.regression.new_entry --help`: 0.

Do not run `tests.regression.new_entry` without `--help` to try it out. It appends a row to
`tests/regression/LOG.md`.

## Markers and flags

Registered in `tests/conftest.py`. The `pyproject.toml` `addopts` include `--strict-markers`, which
makes pytest reject any marker that is not registered.

| Marker or flag | Meaning | Default |
|---|---|---|
| `@pytest.mark.network` | makes live network calls | skipped unless `--run-network` |
| `@pytest.mark.sim` | needs Windows, MSFS 2024 and the SDK | skipped unless `--run-sim`; always skipped off Windows |
| `@pytest.mark.slow` | takes more than about 10 s | runs; deselect with `-m "not slow"` |
| `--update-golden` or env `PALMFIX_UPDATE_GOLDEN=1` | rewrite golden files instead of comparing | off; refused when env `CI` is set |

Network guard: `pytest-socket` is **not** installed (not in the `dev` extra), so
`--disable-socket` is rejected (`unrecognized arguments`). The plan asked for it
(`plans/detailed/06-testing.md` "Pytest configuration requested from ARCH-001"). The guard that
runs is the fallback in `tests/conftest.py`: an autouse fixture patches `socket.socket.connect`
and `connect_ex` for non-loopback IPv4 and IPv6 addresses and raises
`RuntimeError("network disabled in tests: use tests/fixtures or mark @pytest.mark.network")`.
It applies only under pytest. Plain Python can still open sockets. Its self-tests are in
`tests/unit/helpers/test_conftest.py`. The gap is logged on ARCH-001.

## Golden files

- Golden files live in `tests/golden/<case>/expected/`. GEN owns the cases. The `input/` subtree
  is never touched by updates.
- Comparison normalises CRLF and CR to LF and ends the text with one LF, so a Windows checkout
  does not cause false failures. Pass `normalize=None` for raw bytes.
- A missing golden file fails with `GoldenMismatch` and tells you to run `--update-golden`.
- To accept new output: run `python -m pytest --update-golden`, open `git diff` on the golden
  files, and commit them in their own commit. A reviewer reads that diff. Never update goldens
  in the same commit as a code change that causes them.
- Under `CI` (GitHub Actions sets it), an update raises `RuntimeError: refusing to update golden
  files in CI`. Checked: the error is raised on the first golden check that tries to write, not
  when pytest starts.

## Fixture policy

- Keep each fixture under 1 MB. Trim records rather than commit a full download.
- Every fixture directory has a `SOURCES.md` with one line per file: URL, date fetched, licence
  note. **Gap:** none of the fixture directories on main have one yet. Add it with the next
  fixture change.
- No test makes a live call unless it is marked `network`. The guard enforces this.
- Raw downloads go in `data/`, which is gitignored, and are never committed.

## CI wiring

### Local CI (current)

**The GitHub Actions workflows are disabled** in the repository settings (2026-11-22, at the
user's request). CI runs locally instead, with one command that mirrors both workflows:

```bash
python scripts/ci.py --install   # once: create .venv with dev,scan,lidar,gen
python scripts/ci.py             # ruff check, ruff format --check, mypy, pytest + coverage gate, tasks validate/conflicts
python scripts/ci.py --quick     # same, skipping tests marked slow
```

It exits 0 only if every step passes. Run it before merging a task branch into `main`. The
integrator runs it on `main` after every merge, before pushing. To turn GitHub CI back on:
`gh workflow enable python` and `gh workflow enable tracking`. The workflow files below are kept
unchanged so that works.

Differences from the GitHub runs: the local run uses this machine's Python (3.14 on the dev box)
instead of 3.12, and one OS instead of the Ubuntu + Windows matrix. The slow CHM benchmark uses
its 30 s budget locally (120 s only when the `CI` env var is set).

### What the disabled workflows ran

`.github/workflows/python.yml` (triggers on `main` pushes and PRs that touch code, tests,
`schemas/`, `regions/` or the workflow):

- `lint`, `ubuntu-latest`, Python 3.12: `pip install -e ".[dev,scan,lidar,gen,fx]"`, then
  `ruff check .`, `ruff format --check .`, `mypy`.
- `test`, matrix `ubuntu-latest` and `windows-latest`, Python 3.12, same install, then
  `pytest -m "not network and not sim" --cov=palmcore --cov-report=term-missing --cov-fail-under=85`.
- Concurrency group `python-${{ github.ref }}` cancels superseded runs.

`.github/workflows/tracking.yml` (PRs and `main` pushes): `python3 scripts/tasks.py validate`,
`conflicts` (informational), `board`. On Ubuntu this is fine, since `python3` exists there.

### Pytest config on main

From `pyproject.toml` `[tool.pytest.ini_options]`:

- `testpaths = ["tests"]`, `pythonpath = ["."]` (so `import tests.helpers` and
  `python -m tests.<layer>.<tool>` work).
- `addopts = ["--import-mode=importlib", "-ra", "--strict-markers"]`. `importlib` mode lets
  duplicate `test_*.py` basenames live in different packages.
- Markers `network`, `sim`, `slow`. The flags are added in `conftest.py`.

### Test dependencies

Test code needs the `dev` extra (`pytest`, `pytest-cov`, `numpy`, `scipy`, `shapely`, `pyproj`,
`lxml`, `pillow`, `scikit-image`, `jsonschema`, `pyyaml`), plus `gen` for `palmgen` tests
(`jinja2`). CI installs `dev,scan,lidar,gen`. `pytest-socket` is not in any extra. The `pdal`
extra stays out of CI on purpose (native library).

### Line endings (`.gitattributes`)

`* text=auto eol=lf` keeps text files as LF in the repository and in every working tree, Windows
included. Byte-for-byte comparisons (golden files, generated XML) then match between a Windows
checkout and the Linux CI checkout. The binary entries (`*.png`, `*.glb`, `*.zip`, ...) are never
converted. `*.bat`, `*.cmd` and `*.ps1` stay CRLF because they are Windows-only scripts. The golden
helper normalises newlines as a second guard.

### Proposal for ARCH (not applied)

The `test` job already runs the default gate, so the only useful addition is a JUnit file and an
artifact upload. Replace the last `run:` line of the `test` job with:

```yaml
      - run: pytest -m "not network and not sim" --cov=palmcore --cov-report=term-missing --cov-fail-under=85 --junitxml=build/test-results.xml -ra
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results-${{ matrix.os }}
          path: build/test-results.xml
```

`build/` is gitignored. The `--junitxml` path was run locally and created the file. The upload
step is not run on GitHub yet. VERIFY: first GitHub run.

## Which tests gate which phase

Copied from `plans/detailed/06-testing.md` "Which tests gate which phase". The plan is the source.

| Gate | Test layers that gate it | TEST tasks to depend on | Pass rule |
|---|---|---|---|
| GATE-P0 | In-sim visual (manual, Phase 0 findings); build check (CLI exit code, SPIKE-004) | none required; TEST-006 recommended | per plan 05 exit criteria |
| GATE-P1 | Unit harness; contract conformance on the Phase 1 output; data accuracy by QA map review (human) | TEST-001, TEST-004, TEST-100 | contract tests pass; at least 90% of visible palms along inventory streets within 3 m (QA map, or `phase1_inventory` profile if T1 ground truth exists) |
| GATE-P2 | Golden files; build checks; in-sim visual at T1 and T3; regression routine baseline | TEST-002, TEST-016, TEST-102, TEST-104 | golden tests pass; `check_build` exit 0; T1/T3 C1, C4, C5 pass at all viewpoints |
| GATE-P3 | In-sim visual at T1 (VP1, VP2, VP3; C3, C7, C8 now apply) | TEST-102 | checklist pass at T1 |
| GATE-P4 | Data accuracy (`lidar_only` at T1+T2, precision at T4); in-sim visual at T2 | TEST-012 | thresholds in `thresholds.yaml` pass; T2 checklist C1, C2 pass |
| GATE-P5 | Performance comparison (LIVE-009 bake-off); soak test (LIVE-101, only if live) | TEST-103, TEST-014 (only if live) | `compare` exit 0 for the chosen variant; `soak` exit 0 |
| GATE-P6 | Per-region contract conformance, spot-check visual, perf over densest area; regression routine | TEST-004, TEST-102, TEST-103, TEST-015 | per region: contract pass; perf within budget |
| GATE-P7 | Optional image-diff scoring of offline frames | TEST-008 (optional) | FX's own criteria |

Gates are owned by plan 05 and are not edited here.

## Not built yet

| Item | Built by |
|---|---|
| `tests/helpers/build_checks.py`, `tests/regression/check_build.py`, `build_history.csv` | TEST-016 |
| Real test sites T1 to T5 (all `placeholder` now), `<site>/flights/` | TEST-100 (human, sim PC) |
| Visual run tools, `PROTOCOL.md`, `tests/visual/` | TEST-102 |
| Image-diff scoring | TEST-008 (optional) |
| Frametime parser, compare, soak, `tests/perf/` | TEST-013, TEST-103, TEST-014 |
| Ground truth, metrics, `tests/accuracy/` | TEST-009, TEST-010, TEST-101, TEST-011 |
| Network accuracy evaluation | TEST-012 |
| Sim-marked pytest tests | the owning tasks; TEST-006 is a manual sim check, not a pytest test |
| Golden cases in `tests/golden/` | GEN tasks |
| Regression baseline row and `R1` to `R4` runs | TEST-104 (sim PC) |
| `SOURCES.md` in fixture directories | the next task that adds fixtures; gap noted above |
