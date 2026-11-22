---
id: TEST-014
title: Build soak-test report tooling for the live spawner
status: done
phase: 5
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#soak-test"
depends_on: [TEST-013]
requires: [none]
agent: test-engineer
estimate_h: 3
touches: [tests/perf/soak.py, tests/perf/soak_config.yaml, tests/perf/SOAK.md, tests/unit/perf/test_soak.py, tests/fixtures/perf/soak/]
owner: claude-agent
branch: task/test-014-build-soak-test-report-tooling-for-the-l
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-014"
updated: 2026-11-22
---

## Goal

`python -m tests.perf.soak <telemetry.jsonl>` checks a 1-hour live-spawner flight log: object count under the cap, zero after shutdown, bookkeeping consistent, no memory growth, no loop stalls. Plus a written soak procedure.

## Context

- Spec: `plans/detailed/06-testing.md#soak-test` and `#soak-telemetry-format`.
- The telemetry format is TEST's request to LIVE. Read `plans/detailed/04-fs2024-integration.md` and LIVE-101 for what palmlive actually logs. If it differs, write an adapter function `read_palmlive_log(path) -> list[dict]` that maps it to the fields in the plan, and note the mapping in SOAK.md. If LIVE hasn't decided yet, log a request on LIVE-101 (`python3 scripts/tasks.py log LIVE-101 "TEST-014 requests telemetry: <link to plan section>"`).
- The 1-hour soak run itself is LIVE-101 (`plans/detailed/04-fs2024-integration.md`, "LIVE-101 (live spawner deliverable)"), output under `tests/perf/soak/<date>/`. This task gives LIVE-101 the procedure and the checker. Log on LIVE-101 that it should depend on TEST-014: `python3 scripts/tasks.py log LIVE-101 "Soak checker and SOAK.md: TEST-014" --by <you>`.
- VERIFY (V10): how to count leftover palm SimObjects independently after palmlive shuts down. Leave it as a VERIFY in SOAK.md; LIVE-101 answers it in its run (LIVE also plans a `cleanup` command and a forced-kill check).

## Steps

1. `tests/perf/soak_config.yaml`: `leak_window_min: 30`, `leak_mb_per_min_max: 1.0`, `max_tick_gap_s: 5`, `min_duration_min: 60`.
2. `tests/perf/soak.py`: parse JSONL; checks S1-S6 from the plan; least-squares slope for S4 (numpy.polyfit, minutes vs MB); output a Markdown report (one line per check with measured value and limit) to stdout or `--out <path>`; exit 0 / 1 / 2. Missing `audit` event: S2 reports "audit missing" and fails unless `--no-audit`.
3. `tests/perf/SOAK.md`: procedure: start palmlive with telemetry on, load the TEST-103 route, loop it for 60 minutes, stop palmlive normally, run the audit (VERIFY V10), copy the log to `tests/perf/soak/<date>/raw/` (gitignored), run `python -m tests.perf.soak tests/perf/soak/<date>/raw/<log>.jsonl --out tests/perf/soak/<date>/report.md`. Add LIVE's forced-kill + restart + `cleanup` check as step S7 (manual, recorded in the report notes).
4. Fixtures (generated in the test, fixed seed, or small committed JSONL in `tests/fixtures/perf/soak/`): a passing 61-minute log; one failing log per check (count over cap, live 3 after shutdown, spawned − removed ≠ live, memory slope 2 MB/min, a 12 s gap, 30 minutes only).
5. `tests/unit/perf/test_soak.py` covering each fixture.

## Acceptance criteria

- [x] S1-S6 implemented with limits from `soak_config.yaml`. (tests/perf/soak.py; 25 tests pass)
- [x] One passing and six failing cases tested. (test_soak.py: 61-min pass; S1..S6 each fail alone)
- [x] SOAK.md procedure written; V10 recorded as VERIFY. (tests/perf/SOAK.md)
- [x] Telemetry format agreed with LIVE, or the request logged on LIVE-101. (request logged on LIVE-101; LIVE has not replied, format is the plan's)

## Verification

```bash
pytest tests/unit/perf/test_soak.py -q
python -m tests.perf.soak --help
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/test-014-build-soak-test-report-tooling-for-the-l worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-014
- 2026-11-22 [claude-agent] Built tests/perf/soak.py (S1-S6, least-squares slope via numpy.polyfit, read_palmlive_log adapter seam, Markdown report, exit 0/1/2); soak_config.yaml limits provisional; SOAK.md procedure with V10 as VERIFY. Config loader and CLI mirror tests/perf/frametimes.py; validators are local copies because the merged ones hard-code 'perf_config.yaml' in messages.
- 2026-11-22 [claude-agent] Tests: tests/unit/perf/test_soak.py 25 passed (passing 61-min run, one failing case per check S1-S6, S2 audit-missing and --no-audit, input errors, config, report, --help). Fixture tests/fixtures/perf/soak/format_example.jsonl is synthetic.
- 2026-11-22 [claude-agent] Status in_progress -> review.
- 2026-11-22 [integrator] Status review -> done.
