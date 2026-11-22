---
id: TEST-103
title: "Performance flight harness: fixed route, capture procedure, dry-run capture"
status: todo
phase: 5
area: TEST
kind: test
plan_ref: "plans/detailed/06-testing.md#perf-procedure"
depends_on: [TEST-013, TEST-100, DEC-005]
requires: [windows-sim, gpu]
agent: test-engineer
estimate_h: 4
touches: [tests/perf/PROCEDURE.md, tests/perf/routes/, tests/perf/perf_config.yaml, tests/perf/runs/, docs/findings/TEST-103.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

A fixed, repeatable 5-minute perf route, a written capture procedure, and one dry-run capture proving the parser reads real capture files correctly. After this, the Phase 5 bake-off is a matter of following PROCEDURE.md 9 times.

## Context

- Spec: `plans/detailed/06-testing.md#perf-procedure` and `#perf-capture-format`. Tools from TEST-013.
- DEC-005 gives the budget and reference hardware/settings. Copy its values into `perf_config.yaml` `budget:` and set `provisional: false`.
- VERIFY items owned here: V4 (sim process name, PresentMon CLI flags, frametime column), V5 (CapFrameX export format and its 1% low definition), V6 (autopilot flight plan or replay for a repeatable route). Answer them in `docs/findings/TEST-103.md` with the tool versions used.
- Route area: the densest palm area of the bake-off region (ask the Phase 5 owner; default T1's surroundings). Flight state per `docs/findings/TEST-006.md`.

## Steps

1. Install PresentMon and/or CapFrameX on the sim PC. Record versions.
2. Find the route method (V6): try loading a flight plan the autopilot follows at 150-300 m AGL over the palm area; else a recorded replay; else a hand-flown heading/altitude-hold line from a fixed start. Pick the most repeatable. Save it in `tests/perf/routes/<route_id>.*` plus `<route_id>.md` (start point, aircraft, altitudes, duration, how to start it).
3. Capture one 5-minute no-fix pass. Record the exact capture command or UI steps (V4: process name, flags; V5: export format).
4. Open the capture file; write the real frametime column name, comment/header format and any time column into `perf_config.yaml` `capture:`. Keep the placeholder names only if they matched.
5. Run `python -m tests.perf.frametimes <capture>` and compare `avg_fps` and p99 frametime with the tool's own summary. They must agree within 1%. If they don't, find out why (trim, definition) and note it. Record which "1% low" definition the tool shows (V5).
6. Copy DEC-005's budget into `perf_config.yaml`; set `provisional: false`.
7. Write `tests/perf/PROCEDURE.md`: setup (graphics profile, background apps closed, same aircraft), the alternating run order (nofix r1, static r1, live r1, nofix r2, ...), whether a restart is needed between variants, capture steps, file naming `captures/<variant>_r<n>.csv`, `run.yaml` template, and the `compare` command.
8. In PROCEDURE.md, state that the Phase 5 bake-off (LIVE-009) uses this procedure with run folders `tests/perf/bakeoff/<date>/`, and other perf runs use `tests/perf/runs/<date>_<label>/`.
9. Commit the dry run as `tests/perf/runs/<date>_dryrun/` (run.yaml + metrics.json; raw capture stays gitignored). Write `docs/findings/TEST-103.md`.

## Acceptance criteria

- [ ] Route file(s) and route description committed; two passes start from the same place and follow the same path (by eye on the map).
- [ ] `perf_config.yaml` column settings confirmed against a real capture; parser agrees with the tool's summary within 1%.
- [ ] Budget copied from DEC-005, `provisional: false`.
- [ ] V4, V5, V6 answered in the findings note.
- [ ] PROCEDURE.md complete enough to run the bake-off without this task file.

## Verification

```bash
python -m tests.perf.frametimes <path-to-dryrun-capture.csv>   # avg_fps within 1% of the tool's summary
grep -n "provisional: false" tests/perf/perf_config.yaml
test -f docs/findings/TEST-103.md && grep -E "V4|V5|V6" docs/findings/TEST-103.md
```

Manual: fly the route twice; overlay both tracks (or compare start/end screenshots) and confirm they match.

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-21 [plan-breakdown] Task created.
