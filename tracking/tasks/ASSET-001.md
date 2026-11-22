---
id: ASSET-001
title: "Write reference sheets for the 5 SoCal palm species"
status: done
phase: 3
area: ASSET
kind: research
plan_ref: "plans/detailed/03-palm-assets.md#w1-reference-and-build-vs-license"
depends_on: []
requires: [network]
agent: asset-pipeline-artist
estimate_h: 5
touches: [assets/reference/washingtonia_robusta.md, assets/reference/washingtonia_filifera.md, assets/reference/phoenix_canariensis.md, assets/reference/syagrus_romanzoffiana.md, assets/reference/archontophoenix_cunninghamiana.md]
owner: claude-agent
branch: task/asset-001-write-reference-sheets-for-the-5-socal-p
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ASSET-001"
updated: 2026-11-22
---

## Goal

One reference sheet per SoCal species in `assets/reference/`. Modelers use them to match trunk shape, crown shape and frond color, and acceptance reviews compare against them.

## Context

- Species keys and short descriptions are in `plans/03-palm-assets.md` section 1, and the distinguishing features table is in the plan_ref's W4 section.
- Links only. Don't commit downloaded photos (see `#large-file-policy`). If you keep local copies, put them in `data/reference/<species_key>/`, which is gitignored.
- Prefer sources with a clear license (Wikimedia Commons, iNaturalist CC-licensed observations, university extension sites). Record the license next to each link. Botanical facts (frond counts, diameters) should cite a source. Where sources disagree, give a range.
- This task needs no Blender and no sim, and it can start right away.

## Steps

1. Create `assets/reference/<species_key>.md` for each of the 5 keys, with these sections: `## Identification`, `## Photos`, `## Proportions`, `## Look-alikes`, `## Color notes`, `## Sources`.
2. Photos: 8-15 links per species, each tagged with what it shows (`whole`, `crown`, `trunk`, `base`, `skirt`) and its license. Include at least 2 photos of street-planted trees in Southern California.
3. Proportions: a table with trunk diameter at base and below the crown, crown diameter, live frond count, frond (blade) length, petiole length, skirt (yes/no/typical extent), and typical mature height. Give min-max ranges and cite the source per row.
4. Look-alikes: how to tell robusta from filifera (trunk thickness, skirt, crown size), and queen from king (crownshaft, trunk rings, leaflet droop). Write it so a modeler can't mix them up.
5. Color notes: frond color at noon in words plus 1-2 approximate sRGB hex samples taken from the linked photos, and trunk color.
6. Check that the W5 starting heights fit the typical heights you found. Note any disagreement at the end of the robusta sheet under `## Notes for W5`.

## Acceptance criteria

- [x] Five files exist, one per species key, each with all six sections.
- [x] Each sheet has at least 8 photo links with a license or source note.
- [ ] Each proportions row has a range and a source.
- [x] The look-alike sections for both pairs (robusta/filifera, queen/king) are present.

## Verification

```bash
ls assets/reference/{washingtonia_robusta,washingtonia_filifera,phoenix_canariensis,syagrus_romanzoffiana,archontophoenix_cunninghamiana}.md
for f in assets/reference/*.md; do grep -c '^## ' "$f"; done   # expect >= 6 per species file
grep -c 'http' assets/reference/washingtonia_robusta.md          # expect >= 8
```
Reviewer: open 3 random photo links per sheet and confirm they show the named species.

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/asset-001-write-reference-sheets-for-the-5-socal-p worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ASSET-001
- 2026-11-22 [claude-agent] 5 sheets written in assets/reference/. Boxes 1,2,4 ticked (6 sections each; 11-14 photo links per species with license; both look-alike pairs). Box 3 left open: rows with no source found are VERIFY (filifera/queen live fronds, petiole lengths, some trunk base values). 42 Commons links verified to exist via API. Plan W5 heights fit; robusta crown (3.5-4.5 m) and filifera crown (4.5/5.5 m) are above extension sources.
- 2026-11-22 [claude-agent] Status in_progress -> review.
- 2026-11-22 [integrator] integrator: accepted with box 3 open — ~6 proportions rows (live frond count filifera/queen; petiole length filifera/queen/Canary/king; some trunk-base values) have no readable published source and stay VERIFY; they are to be measured from the linked reference photos during modelling (ASSET-010 and the per-species model tasks)
- 2026-11-22 [integrator] Status review -> done.
