---
id: SPIKE-004
title: "Measure fspackagetool command-line builds (1 and 1,000 polygons; behaviour with the sim open)"
status: todo
phase: 0
area: SPIKE
kind: spike
plan_ref: "plans/detailed/04-fs2024-integration.md#spike-004-fspackagetool-measurements"
depends_on: [SPIKE-001, SPIKE-002, SPIKE-008]
requires: [windows-sim]
agent: msfs-sdk-specialist
estimate_h: 2.5
touches: [docs/findings/SPIKE-004.md, docs/findings/SPIKE-004/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Hard numbers and exact tool behaviour for `fspackagetool` run from the command line: where it is, what it writes, its exit codes, how long 1 and 1,000 polygons take, whether builds are incremental, and what happens with the sim open. GEN-013 (wrapper), TEST-016 (build checker), LIVE-100 (sim-running warning) and the "build on demand" question (R-09) all depend on this.

## Context

- Required measurements: `plans/detailed/04-fs2024-integration.md#spike-004-fspackagetool-measurements`. Every bullet there must be in the findings note.
- SDK page: Package Tool, https://docs.flightsimulator.com/msfs2024/html/8_SDK_Tools/Package_Tool/Package_Tool.htm . Only the flags `-outputdir` and `-nopause` are known to the plan; check the page or `fspackagetool -help` (VERIFY) for others and record them, but don't rely on undocumented ones.
- Inputs: `spikes/palmfix-spike/` (SPIKE-002, the "same project" of Phase 0 task 6) and the benchmark projects from SPIKE-008 (`make_bench.py`, run on the PC or copied from a Linux run).
- Use PowerShell `Measure-Command` for wall times. Close other heavy programs. 3 runs each.
- Paths below use `C:\palmfix\` as an example working folder; use any folder and write down which.

## Steps

1. Record date, sim version, SDK version, full path of `fspackagetool.exe` and whether it is on `PATH` (from SPIKE-001).
2. Get the benchmark projects: on the PC, `py spikes\fspackagetool-bench\make_bench.py --center <ADR-0005 lon,lat> --out C:\palmfix\bench` (or copy `build/spike-bench/` from a Linux run).
3. With the sim **closed**, build `spikes\palmfix-spike` from a `cmd` window in its folder:
   `fspackagetool palmfix-spike.xml -outputdir C:\palmfix\out\spike -nopause` (VERIFY: the project file name). Record the exact command line, working directory, exit code (`echo %ERRORLEVEL%`), and save stdout and stderr: append `> C:\palmfix\logs\spike-success.log 2>&1`.
4. Directory listing of the output, depth 6: `tree /f C:\palmfix\out\spike > out-tree.txt`. Note where the compiled package folder is, BGL file names, and how BGLs map to scene files.
5. Timings, 3 runs each, sim closed. For each, in PowerShell: `Measure-Command { fspackagetool <project.xml> -outputdir <out> -nopause }`. Delete the output folder before each run so runs are cold:
   - `p1`
   - `p1000x1`
   - `p1000x10`
   - `p1000x10` again after editing one of its 10 scene files (change one vertex by hand), without deleting the output: is it faster (incremental)?
6. `two-files`: build and list output. Does each scene file get its own BGL?
7. `p1-lf` and `p1-crlf`: build both. Do they succeed equally? Compare the BGL file sizes and hashes (`certutil -hashfile <bgl> SHA256`).
8. Failure cases, record exit code and save the full output to a log file for each:
   - `broken` (invalid scene XML) → `broken.log`;
   - a project file path that doesn't exist → `missing-project.log`.
   Note which output lines mark errors and which mark warnings.
9. Sim open: start MSFS 2024 and load into a flight. Run the `p1` build. Does it run, fail, or wait? Exit code and exact message → `sim-open.log`. Open Task Manager, Details tab: record the sim's process name(s) exactly.
10. After each run, check Task Manager for any leftover `fspackagetool` (or child) process. Record whether `-nopause` returns cleanly.
11. Copy into `docs/findings/SPIKE-004/`: all `.log` files, `out-tree.txt`, and `timings.csv` (columns `variant,run,seconds,exit_code,sim_open`). Write `docs/findings/SPIKE-004.md`.

Results table:

| Item | Result |
|---|---|
| Date, sim version, SDK version | |
| `fspackagetool.exe` path; on PATH? | |
| Exact command line and working directory | |
| Exit code: success / broken XML / missing project / sim open | |
| Output layout: compiled package folder, BGL names, BGL per scene file? | |
| Time `p1` (3 runs, s) | |
| Time `p1000x1` (3 runs, s) | |
| Time `p1000x10` (3 runs, s) | |
| Rebuild after one changed file: incremental? time | |
| LF vs CRLF: same result? | |
| Error and warning line patterns | |
| With sim open: runs / fails / waits; message | |
| Sim process name(s) | |
| Leftover processes after `-nopause`? | |
| Is "build on demand" realistic? (one sentence) | |

## Acceptance criteria

- [ ] `docs/findings/SPIKE-004.md` answers every row of the results table and every bullet of the plan 04 SPIKE-004 list.
- [ ] `docs/findings/SPIKE-004/timings.csv` has 3 runs for each of the 4 timing cases.
- [ ] One success log and at least two failure logs are saved in full (GEN-013 copies them as fixtures).
- [ ] The output tree listing is saved.

## Verification

```bash
test -f docs/findings/SPIKE-004.md
python3 -c "import csv; r=list(csv.DictReader(open('docs/findings/SPIKE-004/timings.csv'))); print(len(r), 'rows'); assert len(r) >= 12"
ls docs/findings/SPIKE-004/*.log
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
