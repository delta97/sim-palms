---
id: TEST-017
title: Write the test runbook and CI wiring notes
status: review
phase: 2
area: TEST
kind: doc
plan_ref: "plans/detailed/06-testing.md#pytest-configuration-requested-from-arch-001"
depends_on: [TEST-002, TEST-004, ARCH-001]
requires: [none]
agent: test-engineer
estimate_h: 2
touches: [tests/README.md]
owner: claude-agent
branch: task/test-017-write-the-test-runbook-and-ci-wiring-not
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-017"
updated: 2026-11-22
---

## Goal

`tests/README.md` tells anyone how to run each test layer, which runs in CI and which only on the sim PC, and gives ARCH a ready-to-paste CI job so the Linux-runnable tests gate every merge.

## Context

- Spec: `plans/detailed/06-testing.md` sections "Pytest configuration requested from ARCH-001", "Pytest markers and flags", "Which tests gate which phase".
- CI workflow files belong to ARCH (ARCH-001) and INFRA (`.github/workflows/tracking.yml`). This task does not edit them. Read what ARCH-001 set up.
- What CI can run: `pytest -m "not sim and not network"` (default skips do this already). Never sim, GPU, human or network steps.

## Steps

1. Write `tests/README.md`:
   - Layout table (from the plan's directory layout) with one line per folder.
   - "Run it" table: layer, command, where it runs (CI / Linux / sim PC / human), time.
   - Markers and flags (`network`, `sim`, `slow`, `--run-network`, `--run-sim`, `--update-golden`).
   - Golden update rules (own commit, reviewer looks at the diff; refused in CI).
   - Fixture policy (size limit, SOURCES.md, no live calls).
   - "CI wiring" section: the pytest config ARCH-001 should have, the test dependency list, and a proposed GitHub Actions job (checkout, setup-python 3.12, install dev extra, `pytest -q -ra`, upload `.pytest_cache`-free junit XML via `--junitxml=build/test-results.xml`). Mark it "proposal for ARCH".
   - Which tests gate which phase (copy the table, link to the plan).
2. Compare with ARCH-001's actual pyproject and CI. If anything requested is missing, log it on ARCH-001: `python3 scripts/tasks.py log ARCH-001 "TEST-017: CI/pytest config missing <x>; see tests/README.md#ci-wiring" --by <you>`.
3. Run the full Linux suite once and paste the summary line into the Log.

## Acceptance criteria

- [x] `tests/README.md` covers every layer with a command and where it runs.
- [x] CI wiring section present; gaps in ARCH's setup logged on ARCH-001.
- [x] Full Linux suite result recorded in the Log.

## Verification

```bash
pytest -q -ra   # sim and network tests reported as skipped, everything else passes
grep -n "CI wiring" tests/README.md
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/test-017-write-the-test-runbook-and-ci-wiring-not worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-017
- 2026-11-22 [claude-agent] Wrote tests/README.md. Verified on 38b886d: Windows 11 Py 3.14.2 'pytest -q -ra' 760 passed, 1 skipped (skip: palmscan output missing); Ubuntu 24.04 Py 3.12.3 (WSL, CI version) same counts, coverage gate 95.28% (>=85) exit 0; ruff check and format clean; mypy clean (34 files); tracking validate 213 tasks 0 errors. Markers: 0 network, 0 sim, 1 slow tests on this base; --run-network and --run-sim deselect all. Golden: CI=1 update raises RuntimeError. palmfix exit codes checked (validate 0/3/2, regions --check 0, config missing region 2). Gaps logged on ARCH-001 (pytest-socket missing; .[dev] alone cannot collect palmgen tests).
- 2026-11-22 [claude-agent] Spec discrepancies: (a) the task Verification says python3 and 'pytest -q -ra' with sim/network skipped; python3 does not exist on the Windows box, so python was used; the skip line for sim and network does not appear because no such tests exist on main. (b) main is 19 commits ahead of the branch base 38b886d (palmscan and palmgen tests added); the files this README depends on are identical on main (c4f5b50), so the commands apply, but the pass count on main will be higher. The README does not pin counts. (c) tests/unit fixture dirs have no SOURCES.md yet (plans/detailed/06 fixture policy); noted in README, not fixed here, since fixtures are owned by their area tasks. (d) the plan's pytest-socket and junit proposal: the existing python.yml test job already runs the default gate; the junit upload is a proposal in README for ARCH, not applied.
- 2026-11-22 [claude-agent] Acceptance: ticked 1 (README covers every layer), 2 (CI wiring section present; gaps logged on ARCH-001), 3 (Linux suite result in this Log: Ubuntu 24.04 Py 3.12.3 760 passed, 1 skipped, coverage 95.28%). Discrepancy handling: the README CI wiring section is the proposed job, not applied to python.yml (ARCH owns it).
- 2026-11-22 [claude-agent] Status in_progress -> review.
