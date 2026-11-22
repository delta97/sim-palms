---
id: ASSET-051
title: "King palm: LOD0 models for all 2 height variants"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w4-blender-scene-conventions"
depends_on: [ASSET-050]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 6
touches: [assets/blender/archontophoenix_cunninghamiana/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

LOD0 meshes for every `archontophoenix_cunninghamiana` variant (short/tall), each 3000-6000 triangles, matching the reference sheet and the variant targets in `assets/species/archontophoenix_cunninghamiana.yaml`.

## Context

- Species features: Smooth ringed trunk (texture); green crownshaft (own material); arching pinnate fronds with leaflets that hang down.
- Notes: The bright green crownshaft between trunk and crown is the defining feature against queen palm. Give it its own material `mat_archontophoenix_cunninghamiana_crownshaft` and texture `tx_archontophoenix_cunninghamiana_crownshaft_albedo.png`. The trunk rings are texture. Fronds arch, and leaflets hang vertically from the rachis.
- Origin at the trunk base, trunk sunk 0.15 m, upright, transforms applied (`#w4-blender-scene-conventions`). Variants are rebuilt, not uniformly scaled (`#w5-height-variants`).
- Model the medium (or first) variant fully, then derive the others.
- If DEC-002 chose license or hybrid, replace modeling steps with 'import the licensed model, fix origin/scale/orientation to the conventions, rebuild materials to the W7 rules', and record the license terms and file source in `textures/SOURCES.md`.

## Steps

1. Model the first variant's trunk (12-16 sides, taper from the reference proportions, base extending to z=-0.15).
2. Build the crown from instanced master fronds at the reference frond count, and add the species-specific parts (see notes).
3. Derive the other variants: change trunk length most, diameter less, crown least. Vary frond arrangement.
4. Name objects `palmfix_archontophoenix_cunninghamiana_<variant>_LOD0_<part>` and apply transforms.
5. Render each variant next to a reference photo at the same scale, and record the image paths in the Log.

## Acceptance criteria

- [ ] 2 LOD0 meshes, each with 3000-6000 triangles.
- [ ] Heights are within ±2% of the yaml targets, with the base at the origin.
- [ ] Side-by-side renders against references are logged.

## Verification

Export LOD0s to `build/archontophoenix_cunninghamiana-lod0/`, then for each variant:
```bash
python -c "from palmcore.assets.gltf_stats import read_gltf as r; s=r('build/archontophoenix_cunninghamiana-lod0/palmfix_archontophoenix_cunninghamiana_<variant>_LOD0.gltf'); print(s.triangles, s.bbox_min, s.bbox_max)"
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
