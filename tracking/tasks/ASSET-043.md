---
id: ASSET-043
title: "Queen palm: in-sim acceptance review"
status: todo
phase: 3
area: ASSET
kind: test
plan_ref: "plans/detailed/03-palm-assets.md#w11-acceptance-review"
depends_on: [ASSET-042]
requires: [windows-sim, human, blender]
agent: asset-pipeline-artist
estimate_h: 2
touches: [assets/species/syagrus_romanzoffiana.yaml, assets/reviews/syagrus_romanzoffiana.md, tests/visual/lineup-syagrus_romanzoffiana/, assets/blender/syagrus_romanzoffiana/, assets/PackageSources/modelLib/syagrus_romanzoffiana/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`syagrus_romanzoffiana` passes the W11 acceptance checklist in the sim and is marked `status: accepted` in its species yaml, ready for ASSET-100 to integrate.

## Context

- Procedure and checklist: `#w11-acceptance-review`. Robusta's review (`assets/reviews/washingtonia_robusta.md`) is the worked example. Screenshot conventions come from TEST-102.
- Build `palmfix-assets` locally, including this species. Don't commit the package definition or `assets/manifest.json`; ASSET-100 does that.
- Small fixes (about 1 h total) can be done here in Blender and re-exported. Bigger fixes become a new task, and this one goes to `blocked`.

## Steps

1. Run `python -m palmcore.assets check --species syagrus_romanzoffiana`. It must show 0 errors.
2. Build `palmfix-assets` locally (fspackagetool, as in ASSET-014) and load it in Dev Mode.
3. Place all variants 15 m apart on flat ground and record the coordinates in `assets/reviews/syagrus_romanzoffiana.md`.
4. Take screenshots at 2 m, 150 m and 600 m, at noon and at golden hour, saved to `tests/visual/lineup-syagrus_romanzoffiana/<YYYY-MM-DD>/`.
5. Do a slow fly-away and note the LOD pops. Check base contact and compare with the reference photos.
6. If this species occurs at a test site in palms.geojson and GEN placement exists, review it there too.
7. Fill in the checklist. When everything passes and the user has signed off, set `status: accepted` in `assets/species/syagrus_romanzoffiana.yaml`.

## Acceptance criteria

- [ ] The review file has coordinates, a fully ticked checklist and the user's sign-off.
- [ ] Screenshots for all 6 view/time combinations are saved.
- [ ] `assets/species/syagrus_romanzoffiana.yaml` has `status: accepted`.

## Verification

```bash
python -m palmcore.assets check --species syagrus_romanzoffiana; echo $?   # 0
grep -n 'status: accepted' assets/species/syagrus_romanzoffiana.yaml
ls tests/visual/lineup-syagrus_romanzoffiana/*/ | wc -l                     # >= 6
```
Manual: the user reviews the screenshots and signs off in `assets/reviews/syagrus_romanzoffiana.md`.

## Log

- 2026-11-21 [plan-breakdown] Task created.
