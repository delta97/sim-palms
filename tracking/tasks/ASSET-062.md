---
id: ASSET-062
title: "Royal palm: low-detail model, two variants, LODs and export"
status: todo
phase: 6
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w13-florida-set"
depends_on: [ASSET-060]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 6
touches: [assets/species/roystonea_regia.yaml, assets/blender/roystonea_regia/, assets/PackageSources/modelLib/roystonea_regia/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`roystonea_regia` has 2 low-detail variants (LOD0 ≤ 3000 triangles) with LOD1-3, exported into `assets/PackageSources/modelLib/roystonea_regia/`, passing `python -m palmcore.assets check --species roystonea_regia`.

## Context

- Low-detail rules (`#w13-florida-set`): 2 variants, LOD0 ≤ 3000 triangles (`florida_lod0_max` in budgets.yaml), textures at half the W7 sizes. All other conventions as for SoCal (`#w4-blender-scene-conventions`, `#w6-lods-and-budgets`, `#w7-materials-and-textures`).
- Features: Smooth, pale grey, concrete-like trunk swelling mid-height; long green crownshaft; arching pinnate fronds.
- Reference: `assets/reference/roystonea_regia.md`, with variant heights from its `## Notes for W5`.
- Closest SoCal model to start from: `assets/blender/archontophoenix_cunninghamiana/archontophoenix_cunninghamiana.blend` (copy its frond masters and scene setup).
- Don't write `assets/manifest.json` or the package definition (ASSET-065 integrates).
- Textures must be CC0 or self-made, recorded in `assets/blender/roystonea_regia/textures/SOURCES.md`.

## Steps

1. Write `assets/species/roystonea_regia.yaml` with `set: florida`, `status: draft`, and 2 variants from the reference sheet.
2. Create `assets/blender/roystonea_regia/roystonea_regia.blend` from the archontophoenix_cunninghamiana scene setup. Make the textures and materials (half size).
3. Model LOD0 for both variants (≤ 3000 triangles), then LOD1-3 (Auto LODs, cards, crossed quads).
4. Export to `assets/PackageSources/modelLib/roystonea_regia/`, run `stamp-guids` if needed, then run `python -m palmcore.assets check --species roystonea_regia` and fix every ERROR.
5. Run `python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json`, then `validate --manifest build/manifest.preview.json`.

## Acceptance criteria

- [ ] Both variants exist with 4 LODs each, and LOD0 has 3000 triangles or fewer.
- [ ] `check --species roystonea_regia` exits 0.
- [ ] The preview manifest validates.

## Verification

```bash
python -m palmcore.assets check --species roystonea_regia; echo $?   # 0
python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json && python -m palmcore.assets validate --manifest build/manifest.preview.json; echo $?
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
