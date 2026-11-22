---
id: ASSET-065
title: "Florida set: acceptance review in the sim and manifest/package update"
status: todo
phase: 6
area: ASSET
kind: test
plan_ref: "plans/detailed/03-palm-assets.md#w13-florida-set"
depends_on: [ASSET-061, ASSET-062, ASSET-063, ASSET-064, GATE-P5]
requires: [windows-sim, human]
agent: asset-pipeline-artist
estimate_h: 4
touches: [assets/manifest.json, assets/library.yaml, assets/PackageDefinitions/palmfix-assets.xml, assets/reviews/florida.md, tests/visual/lineup-florida/, assets/species/sabal_palmetto.yaml, assets/species/roystonea_regia.yaml, assets/species/cocos_nucifera.yaml, assets/species/wodyetia_bifurcata.yaml]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

The 4 Florida species pass a combined in-sim acceptance review, are `accepted`, and are included in a new `palmfix-assets` minor version (1.1.0), with their fallbacks removed from `library.yaml`.

## Context

- Checklist and procedure: `#w11-acceptance-review`, applied at low-detail expectations (judge at 150 m and 600 m mainly; street level only needs to look acceptable).
- GATE-P5 is a dependency so that this task can't run while ASSET-101 (Phase 5) is building wrappers. If wrappers exist, re-run ASSET-101's generator afterwards so Florida variants get wrappers too (log a follow-up task).
- Version bump: 1.1.0 in `assets/library.yaml` and the package definition.

## Steps

1. Run `python -m palmcore.assets check` for each Florida species. Each must show 0 errors.
2. Build `palmfix-assets` locally with the Florida species and load it in Dev Mode.
3. Lineup: place both variants of each species in rows 15 m apart on flat ground, and record the coordinates in `assets/reviews/florida.md`.
4. Take screenshots at 2 m, 150 m and 600 m, noon and golden hour, saved to `tests/visual/lineup-florida/<YYYY-MM-DD>/<species>_<view>_<time>.png`.
5. Fill in the W11 checklist per species and get the user's sign-off. Set `status: accepted` in each species yaml that passes.
6. In `assets/library.yaml`, remove the fallback entries for accepted Florida species and set `package_version: 1.1.0`. Set the same in the package definition.
7. Run `build-manifest` and `validate`, then build the package with fspackagetool (exit 0).
8. If SimObject wrappers exist (ASSET-101 done), create a follow-up task to regenerate them.

## Acceptance criteria

- [ ] The review file has a ticked checklist and the user's sign-off per accepted species.
- [ ] The manifest includes the accepted Florida species. `validate` and `build-manifest --check` exit 0.
- [ ] Version 1.1.0 is consistent across library.yaml, the package definition and the manifest. fspackagetool exits 0.

## Verification

```bash
python -m palmcore.assets check; echo $?                 # 0
python -m palmcore.assets build-manifest --check; echo $? # 0
python -m palmcore.assets validate; echo $?               # 0
grep -n 'status: accepted' assets/species/{sabal_palmetto,roystonea_regia,cocos_nucifera,wodyetia_bifurcata}.yaml
```
On the sim PC: build with fspackagetool (exit 0). The user signs off in `assets/reviews/florida.md`.

## Log

- 2026-11-21 [plan-breakdown] Task created.
