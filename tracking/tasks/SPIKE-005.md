---
id: SPIKE-005
title: Test SimConnect static SimObject spawn and whether it survives client disconnect
status: todo
phase: 0
area: SPIKE
kind: spike
plan_ref: "plans/detailed/04-fs2024-integration.md#spike-005-simconnect-spawn-test"
depends_on: [SPIKE-001, SPIKE-009]
requires: [windows-sim]
agent: simconnect-dotnet-engineer
estimate_h: 2
touches: [docs/findings/SPIKE-005.md, docs/findings/SPIKE-005/, spikes/simconnect-persist/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Know, on the current sim update, whether a SimConnect client can put a static SimObject on the ground at a coordinate, how fast, and what happens to it when the client disconnects or crashes. This decides the cleanup logic for live spawning (LIVE-010), feeds the static-vs-live decision (DEC-007, R-11) and the app language choice (DEC-003).

## Context

- Questions to answer: `plans/detailed/04-fs2024-integration.md#spike-005-simconnect-spawn-test`. All of them go in the findings note.
- App: `spikes/simconnect-persist/` from SPIKE-009. Fix compile errors here; keep fixes small and note each one (they are findings about the managed API).
- A "no" is a valid result. The task is done when every question has an answer, not when spawning works.
- Location: the ADR-0005 test block if decided, else any spot with flat open ground (an airport apron works; record the lat/lon).
- Default SimObject title: VERIFY. Look in the sim's installed packages for a simple static or ground object (for example search the `SimObjects` folders for `sim.cfg` files and read their `title=` lines), or use a title from the SDK samples. Record where you found it.

## Steps

1. Build the app: `dotnet build -c Release -p:MsfsSdk="<SDK path>"` in `spikes\simconnect-persist`. Record the managed DLL path and version (file properties > Details), the native DLL path, and whether it loads in a .NET 8 x64 console app. If it doesn't compile, fix and note each change.
2. Start MSFS 2024 and load into a free flight near the spawn location. Note sim version.
3. `badtitle` mode. Record what comes back.
4. `spawn --title "<default title>" --lat <lat> --lon <lon> --hold-s 60`. While it holds, look at the spot: screenshot `spawn.png`. Record: creation latency, does the object sit on the terrain at that lat/lon (on the ground / floating / sunken / offset)?
5. After the app closes cleanly: does the object stay? Wait 60 s and look again. Screenshot `after-clean-disconnect.png`.
6. `remove --ids-file spawned.json`. Does the new connection remove the old object by its old id? Record the output.
7. Repeat step 4 with `--crash`. Does the object stay after the client process dies? Screenshot `after-crash.png`. Then run `remove` again.
8. Spawn one object, leave it, and go back to the main menu, then start a new flight at the same spot. Is it still there?
9. `spawn --count 100 --spacing-m 10 --hold-s 30` (if step 4 worked). Record the total time for 100 creations and any errors. Watch frame rate by eye.
10. Note whether the create call has any scale parameter (expected: no) and whether any other way to scale spawned objects appeared.
11. Record which message-pump pattern worked (wait handle or window message).
12. Save console output of each step as `docs/findings/SPIKE-005/<step>.log` and screenshots in the same folder. Write `docs/findings/SPIKE-005.md`.

Results table:

| Question | Answer |
|---|---|
| Date, sim version, SDK version | |
| Managed DLL path and version; native DLL path | |
| Loads in .NET 8 x64 console app? Code changes needed | |
| Default title used and where it was found | |
| Non-existent title: what happens | |
| Init-position settings used | |
| On terrain at the given lat/lon? | |
| Creation latency (ms) for 1; total time for 100 | |
| Survives clean disconnect? | |
| Survives client crash? | |
| New connection can remove old object by old id? | |
| Survives return to main menu / new flight? | |
| Can spawned objects be scaled? | |
| Message-pump pattern that works | |

## Acceptance criteria

- [ ] `docs/findings/SPIKE-005.md` answers every row of the results table, with sim and SDK versions.
- [ ] Console logs for each step and screenshots for steps 4, 5 and 7 are in `docs/findings/SPIKE-005/`.
- [ ] Any compile fixes are committed in `spikes/simconnect-persist/` and listed in the note.

## Verification

```bash
test -f docs/findings/SPIKE-005.md && grep -iE "disconnect|crash" docs/findings/SPIKE-005.md
ls docs/findings/SPIKE-005/
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
