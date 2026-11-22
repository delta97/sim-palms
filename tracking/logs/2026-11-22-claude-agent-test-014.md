# Session log: 2026-11-22, claude-agent, test-014 soak report tooling

- **Started / ended:** 2026-11-22 (local time)
- **Agent / model / person:** claude-agent (Claude Haiku 5.5)
- **Branch / worktree:** task/test-014-build-soak-test-report-tooling-for-the-l, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-014
- **Tasks:** TEST-014 (in_progress -> review); LIVE-101 (log entries only, status unchanged)

## Goal

Build the soak-test checker and procedure for the live spawner: S1-S6 over a palmlive telemetry JSONL,
a Markdown report, exit codes 0/1/2, and SOAK.md for LIVE-101's 1-hour run.

## What changed

- `tests/perf/soak.py`: reads JSONL (`read_palmlive_log` is the adapter seam), validates, runs S1-S6, writes the report (stdout or `--out`). Least-squares slope via `numpy.polyfit`. Config loader and CLI mirror `tests/perf/frametimes.py`.
- `tests/perf/soak_config.yaml`: the four plan limits plus `provisional: true`.
- `tests/perf/SOAK.md`: checks table, telemetry format, mapping note, LIVE-101 procedure, VERIFY items (V10 audit method, telemetry switch, tick rate, memory measure).
- `tests/unit/perf/test_soak.py`: 25 tests. Logs are generated per test with a fixed seed; one passing 61-minute run, one failing case per check, S2 audit-missing vs `--no-audit`, input errors, config, report file, `--help`.
- `tests/fixtures/perf/soak/format_example.jsonl`: 6-line synthetic example of the plan's format.
- `tracking/tasks/TEST-014.md`: acceptance boxes ticked with evidence; Log entries.
- `tracking/tasks/LIVE-101.md`: two Log entries (checker/SOAK.md ready; telemetry request). No status change. `depends_on` TEST-014 was already present.
- `tracking/logs/2026-11-22-claude-agent-test-014.md`: this file.

## Verification

- `.venv/Scripts/python -m pytest tests/unit/perf/test_soak.py -q`: 25 passed.
- `python -m tests.perf.soak --help`: exit 0.
- `python scripts/tasks.py validate`: 213 tasks, 0 errors, 0 warnings.
- `python scripts/ci.py`: see the commit message / final report for the result.

## Decisions and findings

- palmlive does not exist yet. The telemetry format is the plan's (`#soak-telemetry-format`). LIVE has not confirmed it. Any different palmlive output goes in `read_palmlive_log`.
- All limits (S4 1.0 MB/min over 30 min, S5 5 s, S6 60 min) are the plan's starting values and are marked provisional. The per-tick cap comes from the log, not the config.
- S4 allows one tick gap at the window start, so 1 Hz ticks over a 60-minute run pass.
- The config loader and validators are local copies of the frametimes helpers. The merged ones hard-code "perf_config.yaml" in their error messages. Sharing them needs a small change to `tests/perf/frametimes.py` (outside this task's `touches`).
- LIVE-101's Verification reads `tests/perf/soak/<date>/counts.csv`, but the checker reads JSONL. This needs an adapter or a LIVE decision.
- `tests/README.md` still lists `tests/perf/` soak as not built. Not updated here (not in `touches`).

## Open issues

- V10: independent count of leftover palm SimObjects after shutdown. Method not decided; LIVE-101 answers it.
- Telemetry switch and output path in palmlive: LIVE decides.
- Format agreement with LIVE pending (request logged on LIVE-101).
- Shared config-validator helper with TEST-013 (see above).

## Handoff: next steps

1. Review TEST-014 (code-reviewer), then merge the branch on `main` by the integrator.
2. When LIVE-101 starts: confirm the palmlive telemetry format against `tests/perf/SOAK.md`; add the adapter in `read_palmlive_log` if it differs; decide V10 with LIVE.
3. Optional: move the validators in `tests/perf/frametimes.py` into a shared helper so soak and frametimes use one copy.
