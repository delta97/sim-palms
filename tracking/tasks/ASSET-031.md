---
id: ASSET-031
title: "Canary Island date palm: LOD0 models for all 3 height variants"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w4-blender-scene-conventions"
depends_on: [ASSET-030]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 6
touches: [assets/blender/phoenix_canariensis/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

LOD0 meshes for every `phoenix_canariensis` variant (short/medium/tall), each 3000-6000 triangles, matching the reference sheet and the variant targets in `assets/species/phoenix_canariensis.yaml`.

## Context

- Species features: Thick trunk with a diamond leaf-base pattern (albedo + normal), often a knob of leaf bases under the crown; large round crown of many long pinnate fronds.
- Notes: The crown is large (8-11 m) with 100+ fronds, so the LOD0 budget is tight. Use pinnate frond cards (alpha texture of leaflets on a bent strip of about 20-40 triangles) instead of modeled leaflets. The diamond leaf-base pattern is texture plus normal map, not geometry. Model the knob under the crown as a short bulged section of trunk.
- Origin at the trunk base, trunk sunk 0.15 m, upright, transforms applied (`#w4-blender-scene-conventions`). Variants are rebuilt, not uniformly scaled (`#w5-height-variants`).
- Model the medium (or first) variant fully, then derive the others.
- If DEC-002 chose license or hybrid, replace modeling steps with 'import the licensed model, fix origin/scale/orientation to the conventions, rebuild materials to the W7 rules', and record the license terms and file source in `textures/SOURCES.md`.

## Steps

1. Model the first variant's trunk (12-16 sides, taper from the reference proportions, base extending to z=-0.15).
2. Build the crown from instanced master fronds at the reference frond count, and add the species-specific parts (see notes).
3. Derive the other variants: change trunk length most, diameter less, crown least. Vary frond arrangement.
4. Name objects `palmfix_phoenix_canariensis_<variant>_LOD0_<part>` and apply transforms.
5. Render each variant next to a reference photo at the same scale, and record the image paths in the Log.

## Acceptance criteria

- [ ] 3 LOD0 meshes, each with 3000-6000 triangles.
- [ ] Heights are within ±2% of the yaml targets, with the base at the origin.
- [ ] Side-by-side renders against references are logged.

## Verification

Export LOD0s to `build/phoenix_canariensis-lod0/`, then for each variant:
```bash
python -c "from palmcore.assets.gltf_stats import read_gltf as r; s=r('build/phoenix_canariensis-lod0/palmfix_phoenix_canariensis_<variant>_LOD0.gltf'); print(s.triangles, s.bbox_min, s.bbox_max)"
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
