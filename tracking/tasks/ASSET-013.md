---
id: ASSET-013
title: "Mexican fan palm: LOD1-LOD3 for all three variants"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w6-lods-and-budgets"
depends_on: [ASSET-012]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 4
touches: [assets/blender/washingtonia_robusta/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Every robusta variant has LOD1 (800-1500 triangles), LOD2 (150-300, frond cards) and LOD3 (under 50, crossed quads with a baked silhouette), keeping LOD0's height and crown extent so switches don't change size.

## Context

- Method and budgets: `#w6-lods-and-budgets`. Try the exporter's Auto LODs first (how to configure it is in TOOLCHAIN.md from ASSET-004), then hand-fix.
- LOD2/LOD3 need a baked card texture `tx_washingtonia_robusta_cards_albedo.png` (1024x1024 or smaller, RGBA). Bake it from LOD0 with orthographic side renders and transparent film. Add it to `textures/SOURCES.md` as 'baked from LOD0'.
- Materials allowed: up to 3 per LOD, and 1 at LOD3.

## Steps

1. For each variant, generate LOD1 with Auto LODs (or Decimate on an export copy). Fix fronds that collapsed, keep the outer silhouette fronds, and use an 8-sided trunk.
2. Bake `tx_washingtonia_robusta_cards_albedo.png`: render the medium LOD0 crown from 2-3 side angles plus the whole tree, packed into one atlas.
3. LOD2: replace each frond (or groups of fronds) with single bent quads mapped to the cards atlas, and use a 6-sided trunk. Stay within 150-300 triangles.
4. LOD3: 2-3 vertical crossed quads covering the full tree height, mapped to the whole-tree silhouette. One material. Fewer than 50 triangles.
5. Check that each LOD's top height is within 3% of LOD0 and its crown extent within 20%.

## Acceptance criteria

- [ ] 12 LOD meshes exist (3 variants x 4 LODs), named per the naming table.
- [ ] Triangle counts are within the W6 budgets (Blender statistics or a check run).
- [ ] The cards texture exists, is power-of-two, and is listed in SOURCES.md.

## Verification

Export all variants and LODs to `build/robusta-all/` in the PackageSources layout, then:
```bash
python -m palmcore.assets check --species washingtonia_robusta --assets-dir build/robusta-all   # expect 0 errors on LOD count, triangle budget, monotonic, height
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
