---
id: SPIKE-006
title: Place one default library tree as a stand-in in the cut hole
status: todo
phase: 0
area: SPIKE
kind: spike
plan_ref: "plans/detailed/05-phases.md#phase-0-feasibility-spike"
depends_on: [SPIKE-002]
requires: [windows-sim, human]
agent: msfs-sdk-specialist
estimate_h: 1
touches: [docs/findings/SPIKE-006.md, docs/findings/SPIKE-006/, spikes/palmfix-spike/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

One default library object (any tree, ideally a palm) stands in the SPIKE-002 hole, sitting on the ground. Its name, GUID and rough height are recorded, because Phase 2 uses it as the placeholder model.

## Context

- Phase 0 task 3 in `plans/05-phases.md`. Phase 0 exit criterion: "a stand-in tree placed".
- `palmgen` writes this object's GUID into `templates.yaml` `placeholder_model` (`plans/detailed/04-fs2024-integration.md#template-placeholder-conventions`), so the GUID must be copied exactly.
- Ground snapping matters: R-17 (bases float or sink because sim terrain under the cut differs from the photogrammetry surface).
- SDK page for scenery objects: https://docs.flightsimulator.com/msfs2024/html/5_Content_Configuration/Environment/Scenery_Objects/Scenery_XML_Properties.htm

## Steps

1. Open `palmfix-spike` with the SPIKE-002 cut. Slew to the cut.
2. In the Scenery Editor, open the object library (VERIFY: panel name). Search for "palm", then "tree". Pick one object. Record its display name and GUID (VERIFY: where the editor shows the GUID; if it doesn't, it will be in the saved scene XML after step 6).
3. Place it in the middle of the hole. Turn on snap to ground if the editor offers it (VERIFY: option name). Record whether snapping is a property of the object or an editor action.
4. Build and look at street level and 300 m. Screenshots `standin-street.png`, `standin-300m.png`.
5. Check the base: floating, sunken, or on the ground. Estimate the object's height (compare with a nearby car about 1.5 m tall, or a street light about 8 m tall).
6. Save the scene. Open the saved scene XML in a text editor and find the object entry. Copy that fragment into the findings note.
7. Copy the updated project source files into `spikes/palmfix-spike/` (overwrite the SPIKE-002 copy).
8. Write `docs/findings/SPIKE-006.md` with the results table; screenshots go in `docs/findings/SPIKE-006/`.

Results table:

| Question | Answer |
|---|---|
| Date, sim version, SDK version | |
| Object display name | |
| Object GUID (exact, as in the XML) | |
| Approximate height (m) | |
| Snap to ground: property, editor action, or none | |
| Base on the ground? (yes / floating / sunken, by how much) | |
| Looks acceptable as a stand-in at 300 m? | |
| Saved XML fragment for the object | |

## Acceptance criteria

- [ ] `docs/findings/SPIKE-006.md` gives the object's display name, exact GUID, approximate height and base result.
- [ ] Street-level and 300 m screenshots are in `docs/findings/SPIKE-006/`.
- [ ] The saved XML fragment for the object is quoted in the note.
- [ ] `spikes/palmfix-spike/` contains the updated scene with the object.

## Verification

```bash
grep -iE "guid" docs/findings/SPIKE-006.md
ls docs/findings/SPIKE-006/
```

Manual: the reviewer checks that the GUID in the note matches the one in `spikes/palmfix-spike/` scene XML (`grep -ri "<guid from note>" spikes/palmfix-spike/`).

## Log

- 2026-11-22 [plan-breakdown] Task created.
