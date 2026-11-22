---
id: SPIKE-002
title: Cut one photogrammetry palm blob with Exclude TIN and the vegetation exclude
status: in_progress
phase: 0
area: SPIKE
kind: spike
plan_ref: "plans/detailed/05-phases.md#phase-0-feasibility-spike"
depends_on: [SPIKE-001, DEC-004]
requires: [windows-sim, human]
agent: msfs-sdk-specialist
estimate_h: 2
touches: [docs/findings/SPIKE-002.md, docs/findings/SPIKE-002/, spikes/palmfix-spike/]
owner: user
branch: main
worktree: ""
updated: 2026-11-22
---

## Goal

Answer the project's make-or-break question: on the current sim update, does one polygon with Exclude TIN and the vegetation exclude remove one photogrammetry palm blob in a native 2024 project? Also record what is left under the cut and whether autogen trees fill the hole.

## Context

- Phase 0 task 2 in `plans/05-phases.md`. Kill criterion K1 (`plans/detailed/07-risks-and-open-questions.md#kill-criteria`): if Exclude TIN or the vegetation exclude does not remove the blob, the project pauses.
- Test block: ADR-0005 from DEC-004 (street, centre point, slew start position). Use a blob on that street that is at least 10 m from any building (the building case is SPIKE-007).
- SDK page: Polygon Objects (Exclude TIN, vegetation exclude): https://docs.flightsimulator.com/msfs2024/html/2_DevMode/Scenery_Editor/Objects/Polygon_Objects.htm
- Known bug history: DevSupport thread on SU6 beta exclusions (https://devsupport.flightsimulator.com/t/su6-beta-exclusions-of-any-type-not-working-rectangle-water-etc/18156). RISK-005's first pass records the current status; read it before starting.
- If TEST-006 is done, use its screenshot and camera method. If not, use any method and note it.
- The project you change here is copied into the repo at `spikes/palmfix-spike/` (source files only). TEST-104's regression routine rebuilds it after every sim update (its V11 item), so keep it small.

## Steps

1. Open `palmfix-spike` (SPIKE-001) in Dev Mode. Slew to the ADR-0005 start position.
2. Pick one clear palm blob away from buildings. Record its approximate lat/lon (VERIFY: where Dev Mode shows the cursor or camera coordinates).
3. Take "before" screenshots of the blob: `before-street.png` (camera about 2 m above the street, 20-30 m away) and `before-300m.png` (about 300 m up, looking down at about 45 degrees).
4. Open the Scenery Editor (VERIFY: menu path). Add a polygon object (VERIFY: object type name). Draw it around the blob with 6 or more vertices, about 1-2 m outside the blob's visible edge.
5. In the polygon's properties, turn on Exclude TIN only. VERIFY: exact property names. Build (Project Editor build), then look at the blob from the same two views. Screenshots `tin-only-street.png`, `tin-only-300m.png`.
6. Turn on the vegetation exclude as well (VERIFY: exact property name). Build and look again. Screenshots `tin-veg-street.png`, `tin-veg-300m.png`.
7. Note what you see under the cut at both heights: flat ground texture, aerial image, a hole, terrain spikes, sharp edges, colour seams.
8. Note whether autogen (procedural) trees appear inside the polygon with TIN only, and with TIN + vegetation exclude. Wait about 30 s and move the camera a little in case they stream in late.
9. Save the scene in the editor. Close and reopen the project, build again, and confirm the cut is still there.
10. Copy the project's source files (project XML, PackageDefinitions, scene XML; not the built output) into the repo at `spikes/palmfix-spike/`, keeping the folder structure. Add `spikes/palmfix-spike/README.md` with one line each: sim version, SDK version, what the scene contains.
11. Save screenshots into `docs/findings/SPIKE-002/` (PNG or JPEG, ideally under 1 MB each). Fill in the results table and write `docs/findings/SPIKE-002.md`.

Results table:

| Question | Answer |
|---|---|
| Date, sim version, SDK version | |
| Blob lat/lon | |
| Scenery Editor path to add a polygon; property names used | |
| TIN only: blob gone at street level? at 300 m? (yes / partly / no) | |
| TIN only: autogen trees in the hole? | |
| TIN + vegetation exclude: blob gone at street level? at 300 m? | |
| TIN + vegetation exclude: autogen trees in the hole? | |
| What is left under the cut (street level) | |
| What is left under the cut (300 m) | |
| Does the cut survive save, close, reopen and rebuild? | |
| K1 verdict: does the trick work on this update? (yes / no) | |

## Acceptance criteria

- [ ] Before, TIN-only and TIN+vegetation screenshots at street level and 300 m are in `docs/findings/SPIKE-002/`.
- [ ] `docs/findings/SPIKE-002.md` answers every row of the results table, with sim and SDK versions.
- [ ] The K1 verdict is stated as yes or no, in one sentence, at the top of the note.
- [ ] `spikes/palmfix-spike/` holds the project source files and a README with versions.

## Verification

```bash
test -f docs/findings/SPIKE-002.md && grep -i "K1" docs/findings/SPIKE-002.md
ls docs/findings/SPIKE-002/ | wc -l    # expect >= 6 images
ls spikes/palmfix-spike/
```

Manual: a reviewer compares the before and TIN+vegetation screenshots side by side and agrees with the verdict.

## Log

- 2026-11-22 [plan-breakdown] Task created.
- 2026-11-22 [user] Claimed. branch=main worktree=-
- 2026-11-22 [integrator] integrator 2026-11-22: Dev Mode is unstable on this PC, so the cut is written as XML instead of drawn in the Scenery Editor. Polygon format, ExcludeTIN {18B58CBF-...} and VegetationDensity {41EFF715-...} from the SDK docs (Scenery XML Properties + XML Examples pages, read 2026-11-22); scene validates against bglcomp.xsd. Two 12-gon r=6 m polygons in one scene to need only one build: A ExcludeTIN only around sdpb-8a03f7f6752f55c8 (32.794425,-117.251520), B ExcludeTIN + VegetationDensity 0 around sdpb-e6ea40b0410d50ac (32.794239,-117.252341); both 15.2 m W. robusta >=22 m from buildings. Installed in the user's project (empty scene backed up as Scene.xml.empty-backup); sources and generator in spikes/palmfix-spike/. Waiting on the user to build and look.
