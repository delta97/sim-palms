---
id: ASSET-011
title: "Mexican fan palm: LOD0 model of the medium variant"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w4-blender-scene-conventions"
depends_on: [ASSET-010]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 5
touches: [assets/blender/washingtonia_robusta/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`palmfix_washingtonia_robusta_medium_LOD0` is modeled: trunk, live crown and optional short dead-frond skirt. It matches the reference sheet and is within the LOD0 budget (3000-6000 triangles). It's the master the other variants and LODs come from.

## Context

- Distinguishing features (`#w4-blender-scene-conventions` table): very tall thin trunk with a slight flare at the base, small dense fan head, optional short skirt. Don't let it drift toward California fan palm proportions. Check against `assets/reference/washingtonia_robusta.md` `## Look-alikes`.
- Target from the species yaml: medium is about 21 m tall with a 4.0 m crown. Height is measured from the origin (trunk base at z=0) to the highest frond tip.
- Origin and ground sink rules: trunk base center at the world origin, trunk extending to z = -0.15.
- If DEC-002 chose license or hybrid, replace modeling steps with 'import the licensed model, fix origin/scale/orientation to the conventions, rebuild materials to the W7 rules', and record the license terms and file source in `textures/SOURCES.md`.

## Steps

1. Trunk: a 12-16-sided tube along +Z, base diameter and taper from the reference proportions, base flare in the bottom 0.5 m, extending to z=-0.15. UVs tile `tx_washingtonia_robusta_bark_albedo` along V. Aim for about 600-1000 triangles.
2. Crown: instance the master fronds in a spiral, with live fronds pointing up and out and older ones drooping, at about the frond count from the reference sheet. Aim for about 3000-4000 triangles.
3. Optional skirt: a few dead fronds hanging under the crown (robusta is often trimmed; keep it short). Aim for 500 triangles or fewer.
4. Name objects `palmfix_washingtonia_robusta_medium_LOD0_<part>`. Apply transforms. Realize instances in an export copy if TOOLCHAIN.md says instances don't export.
5. Check the triangle count in Blender's statistics overlay. If it's over 6000, reduce frond segments first and keep the frond count.
6. Render a front and a top orthographic view next to a reference photo at the same scale, and save it as `_work` images (not committed) for the Log.

## Acceptance criteria

- [ ] LOD0 medium has 3000-6000 triangles (Blender statistics).
- [ ] Height is 21 m ±2%, with the base at the origin and the trunk sunk 0.15 m.
- [ ] A side-by-side render with a reference photo shows matching trunk taper, crown size relative to height, and frond shape. Attach the image path in the Log.

## Verification

Export LOD0 only to `build/robusta-lod0/` with the TOOLCHAIN.md settings, then:
```bash
python -c "from palmcore.assets.gltf_stats import read_gltf as r; s=r('build/robusta-lod0/palmfix_washingtonia_robusta_medium_LOD0.gltf'); print(s.triangles, s.bbox_min, s.bbox_max)"
```
Expect triangles in 3000-6000, top in 20.6-21.4 (Y up), and bottom in -0.25-0.0.

## Log

- 2026-11-21 [plan-breakdown] Task created.
