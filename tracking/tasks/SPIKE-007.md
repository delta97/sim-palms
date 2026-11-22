---
id: SPIKE-007
title: Cut a palm blob right next to a building and record what happens to the walls
status: todo
phase: 0
area: SPIKE
kind: spike
plan_ref: "plans/detailed/05-phases.md#phase-0-feasibility-spike"
depends_on: [SPIKE-006]
requires: [windows-sim, human]
agent: msfs-sdk-specialist
estimate_h: 1.5
touches: [docs/findings/SPIKE-007.md, docs/findings/SPIKE-007/, spikes/palmfix-spike/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Know what an Exclude TIN cut does to a photogrammetry building wall when the palm is within about 3 m of it, and whether shaping the polygon to stay off the building footprint avoids the damage. This sets how much the generator's building clipping matters (R-03, kill criterion K3).

## Context

- Phase 0 task 4 in `plans/05-phases.md`. ADR-0005 (DEC-004) names a palm within about 3 m of a building wall on the test block.
- Phase 2 clips cuts by building footprints with `exclusion.clip_buffer_m` (default 0.3 m, `plans/detailed/01-architecture.md#ws7-region-config`). This spike gives the first evidence for whether that works.

## Steps

1. Open `palmfix-spike`. Slew to the building-adjacent palm from ADR-0005.
2. Before screenshots: `before-street.png` (street level, wall and blob both visible) and `before-300m.png`.
3. Test A, plain circle: draw a polygon (6+ vertices) around the blob that overlaps the wall by 1-2 m. Exclude TIN + vegetation exclude on. Build. Screenshots `a-street.png`, `a-300m.png`. Note: is the wall cut, missing, see-through, or intact?
4. Test B, clipped: change the polygon so its edge stops about 0.3 m short of the wall (follow the wall line). Build. Screenshots `b-street.png`, `b-300m.png`. Note: is the blob fully gone on the wall side? Is the wall intact?
5. Optional test C: if B leaves a remnant, try 0.1 m and 0.6 m from the wall and note the difference.
6. Save the scene. Copy the project source into `spikes/palmfix-spike/`.
7. Write `docs/findings/SPIKE-007.md` with the results table; screenshots in `docs/findings/SPIKE-007/`.

Results table:

| Test | Wall damage (none / cut / missing / see-through) | Blob remnant on wall side (none / small / large) | Notes |
|---|---|---|---|
| A plain circle overlapping the wall | | | |
| B clipped 0.3 m short of the wall | | | |
| C optional distances | | | |

Plus: date, sim version, SDK version, palm lat/lon, distance from palm to wall (estimate).

## Acceptance criteria

- [ ] Before, test A and test B screenshots at street level and 300 m are in `docs/findings/SPIKE-007/`.
- [ ] The note states, in one sentence each, whether a cut damages walls and whether clipping avoids it.
- [ ] The note gives a recommendation for `clip_buffer_m` (or says the evidence is not enough).

## Verification

```bash
test -f docs/findings/SPIKE-007.md && grep -iE "wall|clip" docs/findings/SPIKE-007.md
ls docs/findings/SPIKE-007/ | wc -l    # expect >= 6 images
```

## Log

- 2026-11-22 [plan-breakdown] Task created.
