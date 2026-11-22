---
id: ASSET-063
title: "Coconut palm: low-detail model, two variants, LODs and export"
status: todo
phase: 6
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w13-florida-set"
depends_on: [ASSET-060]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 6
touches: [assets/species/cocos_nucifera.yaml, assets/blender/cocos_nucifera/, assets/PackageSources/modelLib/cocos_nucifera/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`cocos_nucifera` has 2 low-detail variants (LOD0 ≤ 3000 triangles) with LOD1-3, exported into `assets/PackageSources/modelLib/cocos_nucifera/`, passing `python -m palmcore.assets check --species cocos_nucifera`.

## Context

- Low-detail rules (`#w13-florida-set`): 2 variants, LOD0 ≤ 3000 triangles (`florida_lod0_max` in budgets.yaml), textures at half the W7 sizes. All other conventions as for SoCal (`#w4-blender-scene-conventions`, `#w6-lods-and-budgets`, `#w7-materials-and-textures`).
- Features: Slender, often curved, ringed trunk with a swollen base; pinnate fronds; coconut clusters under the crown.
- Reference: `assets/reference/cocos_nucifera.md`, with variant heights from its `## Notes for W5`.
- Closest SoCal model to start from: `assets/blender/syagrus_romanzoffiana/syagrus_romanzoffiana.blend` (copy its frond masters and scene setup).
- Don't write `assets/manifest.json` or the package definition (ASSET-065 integrates).
- Textures must be CC0 or self-made, recorded in `assets/blender/cocos_nucifera/textures/SOURCES.md`.

## Steps

1. Write `assets/species/cocos_nucifera.yaml` with `set: florida`, `status: draft`, and 2 variants from the reference sheet.
2. Create `assets/blender/cocos_nucifera/cocos_nucifera.blend` from the syagrus_romanzoffiana scene setup. Make the textures and materials (half size).
3. Model LOD0 for both variants (≤ 3000 triangles), then LOD1-3 (Auto LODs, cards, crossed quads).
4. Export to `assets/PackageSources/modelLib/cocos_nucifera/`, run `stamp-guids` if needed, then run `python -m palmcore.assets check --species cocos_nucifera` and fix every ERROR.
5. Run `python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json`, then `validate --manifest build/manifest.preview.json`.

## Acceptance criteria

- [ ] Both variants exist with 4 LODs each, and LOD0 has 3000 triangles or fewer.
- [ ] `check --species cocos_nucifera` exits 0.
- [ ] The preview manifest validates.

## Verification

```bash
python -m palmcore.assets check --species cocos_nucifera; echo $?   # 0
python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json && python -m palmcore.assets validate --manifest build/manifest.preview.json; echo $?
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
