---
id: TEST-006
title: Verify a repeatable flight, camera and screenshot method in MSFS 2024
status: todo
phase: 0
area: TEST
kind: spike
plan_ref: "plans/detailed/06-testing.md#capture-method"
depends_on: []
requires: [windows-sim]
agent: msfs-sdk-specialist
estimate_h: 2
touches: [docs/findings/TEST-006.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

A findings note that says exactly how to (a) reload the same position, time and weather, (b) return the camera to the same three viewpoints, and (c) take and find screenshots, in MSFS 2024 on the current update. The visual and perf protocols depend on this.

## Context

- Spec: `plans/detailed/06-testing.md#capture-method`, VERIFY items V1, V2, V3.
- Don't assume MSFS 2020 behaviour carries over (saved `.FLT` flights, custom camera slots). Test each on the installed 2024 build.
- Findings format: `docs/findings/README.md` (date, sim version, what was tried, what happened, direct answers).
- Any spot works for this test; use the DEC-004 block if it's already chosen.

## Steps

1. Record sim version (and SDK version if installed).
2. **Flight state (V1):** try, in order, and note what works: saving and reloading a flight from the menu; Dev Mode tools for setting aircraft position; setting time to 12:00 local and weather to a clear preset and checking they persist on reload. Record file locations and formats if a file is produced.
3. **Camera (V2):** try the drone camera and any custom-camera save/recall feature. Test whether a saved camera position survives a sim restart. If nothing survives, note a fallback: slew the aircraft to fixed lat/lon/alt/heading (written down) and use a fixed external camera, and measure how close two attempts get (by eye, compare two screenshots).
4. **Screenshots (V3):** take a screenshot with the method you'd use repeatedly (in-sim, Windows Game Bar, NVIDIA, or Print Screen). Note the save folder, file format and resolution.
5. **Package activation (V3):** check whether adding or removing a Community folder package needs a sim restart to take effect. Note how long a restart to a loaded flight takes.
6. Write `docs/findings/TEST-006.md`: one section per question, a direct answer, the exact steps, and a recommended method for each of V1, V2, V3.

## Acceptance criteria

- [ ] Findings note answers V1, V2 and V3 directly, with sim version and date.
- [ ] A recommended, repeatable method for flight state, viewpoint recall and screenshots, with exact steps.
- [ ] Restart requirement for Community package changes recorded.

## Verification

Manual: a second person (or the same person after a sim restart) follows the recommended steps from the note and reaches the same viewpoint; the two screenshots match by eye (same framing, buildings in the same places). Then:

```bash
test -f docs/findings/TEST-006.md && grep -E "V1|V2|V3" docs/findings/TEST-006.md
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
