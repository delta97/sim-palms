---
id: ASSET-012
title: "Mexican fan palm: LOD0 short and tall variants"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w5-height-variants"
depends_on: [ASSET-011]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 3
touches: [assets/blender/washingtonia_robusta/, assets/species/washingtonia_robusta.yaml]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`palmfix_washingtonia_robusta_short_LOD0` and `palmfix_washingtonia_robusta_tall_LOD0` exist, rebuilt from the medium variant with realistic proportions (not a uniform rescale), each within the LOD0 budget.

## Context

- W5 rule: a variant is a rebuild. Trunk length changes most, trunk diameter less, crown least. Young robusta has a relatively bigger crown and thicker trunk for its height. Old, tall robusta has a very thin trunk and a small crown.
- Targets from `assets/species/washingtonia_robusta.yaml`: short 15 m with a 3.5 m crown, tall 28 m with a 4.5 m crown.

## Steps

1. Duplicate the medium LOD0 into the short and tall collections and rename the objects to match.
2. Short: shorten the trunk to hit 15 m total, keep about 90% of medium's trunk diameter, and scale the crown to the 3.5 m target. Optionally use a fuller skirt.
3. Tall: lengthen the trunk to hit 28 m, keep the trunk diameter about the same as medium (robusta stays thin), and scale the crown to 4.5 m.
4. Vary frond arrangement (rotate the spiral start, drop 1-2 fronds) so the variants don't look identical from above.
5. Update the heights or crowns in `assets/species/washingtonia_robusta.yaml` if the modeled values differ from the targets for good reason, and log why.

## Acceptance criteria

- [ ] Both variants have 3000-6000 triangles.
- [ ] Heights are within ±2% of the yaml targets, with the base at the origin.
- [ ] Trunk diameter at 1 m height differs from a uniform scale of medium (for tall, a diameter ratio of 1.15 or less, while the height ratio is 1.33).

## Verification

Export LOD0 of all three variants to `build/robusta-lod0/`, then:
```bash
for v in short medium tall; do python -c "from palmcore.assets.gltf_stats import read_gltf as r; s=r('build/robusta-lod0/palmfix_washingtonia_robusta_'+'$v'+'_LOD0.gltf'); print('$v', s.triangles, round(s.bbox_max[1],2))"; done
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
