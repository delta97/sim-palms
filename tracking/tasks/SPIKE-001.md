---
id: SPIKE-001
title: Install the MSFS 2024 SDK and create an empty Dev Mode scenery project
status: in_progress
phase: 0
area: SPIKE
kind: spike
plan_ref: "plans/detailed/05-phases.md#phase-0-feasibility-spike"
depends_on: []
requires: [windows-sim, human]
agent: msfs-sdk-specialist
estimate_h: 2
touches: [docs/findings/SPIKE-001.md, docs/findings/SPIKE-001/]
owner: user
branch: main
worktree: ""
updated: 2026-11-22
---

## Goal

The MSFS 2024 SDK is installed on the sim PC, Developer Mode works, and an empty native 2024 scenery project named `palmfix-spike` builds from the editor. Every other Phase 0 spike starts from this.

## Context

- Phase 0 task 1 in `plans/05-phases.md`. Breakdown: `plans/detailed/05-phases.md#phase-0-feasibility-spike`.
- The project name uses lowercase letters and hyphens on purpose: plan 04 needs proof that this name style builds (`plans/detailed/04-fs2024-integration.md#spike-003-template-capture`).
- Exclusions have broken on past sim updates. Record the exact sim and SDK versions; every later finding is only valid for those versions.
- SDK docs index: https://docs.flightsimulator.com/msfs2024/html/ (cite the page you used for each step in the findings note).
- Nothing in this runbook is confirmed for MSFS 2024. Each `VERIFY:` line is something to check and write down, not a fact.
- Runs on the user's Windows PC. The msfs-sdk-specialist agent prepares and maintains this runbook and writes up the results; it never fakes them.

## Steps

Before you start: have this task file open, a notes file or this results table ready, and about 2 hours.

1. Record the sim version. VERIFY: where MSFS 2024 shows it (main menu corner, or the About/Credits screen). Write it in the results table.
2. Turn on Developer Mode. VERIFY: menu path (expected under Options > General Options > Developers). Take screenshot `01-devmode-on.png` with the Dev Mode toolbar visible.
3. Download and install the SDK. VERIFY: whether the installer link is in the Dev Mode toolbar (for example Help > SDK Installer) or only on the SDK docs site. Install the core SDK. Record: SDK version, install folder (expected something like `C:\MSFS 2024 SDK\`, VERIFY), and whether the installer set an environment variable (run `set MSFS` in a `cmd` window and copy the output).
4. Find `fspackagetool.exe` in the SDK folder (`where /r "<SDK folder>" fspackagetool.exe`). Record the full path and whether `fspackagetool` runs from a plain `cmd` window without a path (that is, whether it is on `PATH`).
5. Find the SimConnect SDK folder inside the SDK and record the paths of the managed DLL and the native DLL (`where /r "<SDK folder>" *SimConnect*.dll`). SPIKE-005 and SPIKE-009 need them.
6. Create a new project in the Dev Mode Project Editor. VERIFY: menu path (expected File > New Project). Name: `palmfix-spike`. Location: any folder outside the repo, for example `C:\palmfix\palmfix-spike\`. Record the location.
7. Add a package and a scenery asset group if the editor asks for them. VERIFY: the exact wizard steps and the asset group type name for scenery. Write each click down as you go; the next spikes reuse your steps.
8. Build the empty project from the editor. VERIFY: the build button or menu (expected "Build All" in the Project Editor). Record: success or error text, and where the built package was written.
9. Copy the project folder tree listing to `docs/findings/SPIKE-001/tree.txt` (`tree /f "<project folder>" > tree.txt`). This shows where scene XML lives (`scene_dir` in plan 04).
10. Close the sim. Reopen it and reopen the project, to confirm the project reloads. Note anything that had to be redone.
11. Put screenshots (PNG or JPEG, any name) into `docs/findings/SPIKE-001/`. Fill in the results table below and copy it, with your notes, into `docs/findings/SPIKE-001.md` (format: `docs/findings/README.md`). Or paste your raw notes into the task Log and ask an agent to write the note.

Results table (copy into the findings note):

| Item | Result |
|---|---|
| Date | |
| Sim version | |
| SDK version | |
| Dev Mode menu path | |
| SDK install folder | |
| Environment variable set by installer | |
| `fspackagetool.exe` path; on PATH? | |
| SimConnect managed DLL path | |
| SimConnect native DLL path | |
| Project folder | |
| Project Editor steps to create the project (numbered) | |
| Empty project build: ok / error text | |
| Build output folder | |
| Name `palmfix-spike` accepted and built? | |
| Project reopens after restart? | |

## Acceptance criteria

- [ ] `docs/findings/SPIKE-001.md` exists with date, sim version, SDK version and every row of the results table filled (or "not found" with what was tried).
- [ ] The empty `palmfix-spike` project builds from the editor, or the note records the exact error.
- [ ] `docs/findings/SPIKE-001/tree.txt` shows the project folder layout.
- [ ] Each SDK UI step in the note says which `VERIFY:` it confirmed or corrected.

## Verification

```bash
test -f docs/findings/SPIKE-001.md && grep -iE "sim version|sdk version" docs/findings/SPIKE-001.md
test -f docs/findings/SPIKE-001/tree.txt && echo tree-ok
python3 scripts/tasks.py validate
```

A reviewer checks that no row says "assumed".

## Log

- 2026-11-22 [plan-breakdown] Task created.
- 2026-11-22 [integrator] integrator pre-check on this PC (2026-11-22): MSFS 2024 is the Steam edition (app 2537590, buildid 26385953, last updated ~2026-11-07; public SU7.2 1.9.24.0 was 2026-11-05 - in-sim version still to read in step 1). Packages: %APPDATA%\Microsoft Flight Simulator 2024\Packages (Community, Community2024, Official2024, StreamedPackages). SDK not installed: no MSFS* env var, no SDK folder found. Next: the user follows steps 1-3 and 6-8; an agent can do steps 3-5 and 9 (paths, env var, tree listing) once the SDK is installed.
- 2026-11-22 [integrator] Status todo -> in_progress. user started on the sim PC; SDK installed, project created, sim crashed before step 7
- 2026-11-22 [integrator] integrator, read from disk 2026-11-22: SDK 1.8.2 (Core) at C:\MSFS 2024 SDK\, env MSFS2024_SDK (machine), fspackagetool at Tools\bin (not on PATH), SimConnect DLLs at SimConnect SDK\lib and lib\managed. Project palmfix-spike.xml saved in Documents\MyFSProjects (OneDrive) at 14:43:07 with <Packages/>, not built. Sim 1.9.24.0 crashed 14:43:32 (0xe06d7363 then 0xc0000005, WinMain, DevMode=1, world map). Partial findings: docs/findings/SPIKE-001.md. Steps 7-11 remain.
- 2026-11-22 [user] Claimed. branch=main worktree=-
