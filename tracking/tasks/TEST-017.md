---
id: TEST-017
title: Write the test runbook and CI wiring notes
status: in_progress
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

- [ ] `tests/README.md` covers every layer with a command and where it runs.
- [ ] CI wiring section present; gaps in ARCH's setup logged on ARCH-001.
- [ ] Full Linux suite result recorded in the Log.

## Verification

```bash
pytest -q -ra   # sim and network tests reported as skipped, everything else passes
grep -n "CI wiring" tests/README.md
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/test-017-write-the-test-runbook-and-ci-wiring-not worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-017
