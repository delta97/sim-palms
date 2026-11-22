# Soak test: live spawner

Plan: `plans/detailed/06-testing.md#soak-test` (checks) and `#soak-telemetry-format` (log format).
The 1-hour run is LIVE-101 (`plans/detailed/04-fs2024-integration.md`). This file is the procedure
for that run and the reference for the checker `tests/perf/soak.py`. Status: tooling built
(TEST-014). No soak run has been done. palmlive does not exist yet, and DEC-007 may drop live
placement altogether.

## Checks

`python -m tests.perf.soak <telemetry.jsonl>` checks the log. Limits are in
`tests/perf/soak_config.yaml`. They are the plan's starting values and are **provisional**: nothing
here was measured on the live spawner. LIVE-101 records the final values. The per-tick cap (S1)
comes from each record, not from the config.

| Id | Check | Default limit |
|---|---|---|
| S1 | `live <= cap` at every tick | per-tick `cap` |
| S2 | last `shutdown_complete.live == 0` and `audit.palm_objects_found == 0` | 0 and 0 |
| S3 | `spawned_total - removed_total == live` at every tick | exact |
| S4 | least-squares slope of `proc_private_mb` over the last `leak_window_min` minutes | `leak_mb_per_min_max` = 1.0 MB/min (window 30 min) |
| S5 | no gap between consecutive `tick` events longer than `max_tick_gap_s` | 5 s |
| S6 | tick span (first to last tick) | `min_duration_min` = 60 min |
| S7 | forced kill, restart, `cleanup`, no leftovers | manual; not computed by the checker |

S2 with no `audit` event fails with "audit missing". Pass `--no-audit` only when the audit was not
done, and say so in the LIVE-101 log. The report then records "audit skipped".

S4 needs a window at least `leak_window_min` long, allowing for one tick gap. A shorter window fails.

Exit codes: 0 all checks pass, 1 a check failed, 2 bad input (missing or unreadable file, bad JSON
line, missing field, non-integer count, no tick events, timestamps going backwards, naive timestamp,
bad config).

## Telemetry format

JSON Lines, one object per line, UTF-8. `t` is an ISO 8601 time with a time zone (for example
`2027-03-01T14:00:01.250Z`). Times must not go backwards. Events the checker reads:

```json
{"t": "2027-03-01T14:00:01.250Z", "event": "tick", "live": 812, "cap": 2000, "spawned_total": 950, "removed_total": 138, "pending_create": 3, "agl_m": 210.5, "radius_m": 2300.0, "proc_private_mb": 182.4}
{"t": "...", "event": "shutdown_begin"}
{"t": "...", "event": "shutdown_complete", "live": 0}
{"t": "...", "event": "audit", "palm_objects_found": 0}
```

- `tick` needs `live`, `cap`, `spawned_total`, `removed_total`, `proc_private_mb`. Counts are
  integers. `pending_create`, `agl_m` and `radius_m` are logged for the run notes; the checker does
  not read them.
- `shutdown_complete` needs `live`. `audit` needs `palm_objects_found`.
- Other events are ignored. The format example is `tests/fixtures/perf/soak/format_example.jsonl`
  (synthetic).

**Mapping to palmlive.** Not yet decided: LIVE has not built the logger. `read_palmlive_log` in
`tests/perf/soak.py` is the adapter seam. If palmlive writes a different shape (for example a
`counts.csv` as LIVE-101 Step 2 suggests), add the mapping there and record it in this section. The
field meanings stay as the plan defines them.

## Procedure (LIVE-101)

Preconditions: LIVE-011, LIVE-100, ASSET-101, TEST-014 and DEC-007 are done, and DEC-007 picked
live placement. Otherwise the run is not needed.

1. Rebuild the live region and `palmgen index` (LIVE-101 Step 1). Start the sim.
2. Start palmlive with telemetry on, writing to `tests/perf/soak/<date>/raw/<log>.jsonl`. The flag
   or setting name is VERIFY (LIVE decides it).
3. Load the TEST-103 route and fly it in a loop for 60 minutes at steady load. LIVE-101 Step 2 also
   allows low passes and street-level slews, but the checker assumes a steady run.
4. Stop palmlive normally. The log must end with `shutdown_begin` and `shutdown_complete`.
5. Run the independent audit that counts leftover palm SimObjects after shutdown, and write the
   result as an `audit` record with `palm_objects_found`. The method is **VERIFY (V10)**: not
   decided; LIVE-101 confirms it in its run. Do not fill in an audit value by hand.
6. Check the log:
   ```bash
   python -m tests.perf.soak tests/perf/soak/<date>/raw/<log>.jsonl --out tests/perf/soak/<date>/report.md
   ```
   The `raw/` folder is gitignored (`tests/perf/.gitignore`). Commit the report, not the log.
7. S7 (manual): kill the palmlive process, restart it, run `cleanup`, and confirm zero palms
   (visual and count). Record the result in `tracking/logs/LIVE-101.md`. The checker does not
   compute it.
8. Record the final tuned values and the provisional-to-final decision in the LIVE-101 log. If the
   limits change, change `soak_config.yaml` in the same branch and say why.

## VERIFY and open items

- **V10:** how to count leftover palm SimObjects independently after palmlive shuts down. LIVE-101
  answers it. LIVE also plans a `cleanup` command and a forced-kill check (S7).
- Telemetry switch and output path in palmlive: LIVE decides, then the adapter is checked against a
  real log.
- Tick rate: S5 assumes ticks no further apart than 5 s. The plan's spawn loop uses a 1 Hz timer
  (`plans/detailed/04-fs2024-integration.md`, LIVE-004). Confirm it on the first real log.
- Whether `proc_private_mb` is the right memory measure for the sim process: VERIFY on the sim PC.
