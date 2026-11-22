---
id: ASSET-052
title: "King palm: LOD1-LOD3, export and automated checks"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w6-lods-and-budgets"
depends_on: [ASSET-051]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 4
touches: [assets/blender/archontophoenix_cunninghamiana/, assets/PackageSources/modelLib/archontophoenix_cunninghamiana/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Every `archontophoenix_cunninghamiana` variant has LOD1-LOD3 within budget, is exported into `assets/PackageSources/modelLib/archontophoenix_cunninghamiana/`, and passes `python -m palmcore.assets check --species archontophoenix_cunninghamiana` with 0 errors.

## Context

- LOD method, budgets and the cards bake: `#w6-lods-and-budgets`. Robusta's LODs (ASSET-013) are the worked example.
- Export settings: `assets/TOOLCHAIN.md`. Output layout: `#w8-export-and-packaging`.
- Don't write `assets/manifest.json` or the package definition (ASSET-100 integrates). Use the preview manifest in `build/`.

## Steps

1. Make LOD1 (Auto LODs, then hand-fix), LOD2 (cards, 6-sided trunk) and LOD3 (crossed quads with a baked silhouette) for each variant.
2. Bake `tx_archontophoenix_cunninghamiana_cards_albedo.png` and add it to SOURCES.md.
3. Export each variant to `assets/PackageSources/modelLib/archontophoenix_cunninghamiana/palmfix_archontophoenix_cunninghamiana_<variant>/`, with textures in `assets/PackageSources/modelLib/archontophoenix_cunninghamiana/texture/`. Run `stamp-guids --species archontophoenix_cunninghamiana` if TOOLCHAIN.md says it's needed.
4. Run `python -m palmcore.assets check --species archontophoenix_cunninghamiana` and fix every ERROR.
5. Run `python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json`, then `python -m palmcore.assets validate --manifest build/manifest.preview.json`. Leave the species at `status: draft`; the acceptance task sets the status.

## Acceptance criteria

- [ ] `8` LOD files exist under `assets/PackageSources/modelLib/archontophoenix_cunninghamiana/`.
- [ ] `check --species archontophoenix_cunninghamiana` exits 0.
- [ ] The preview manifest validates.

## Verification

```bash
python -m palmcore.assets check --species archontophoenix_cunninghamiana; echo $?    # 0
python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json && python -m palmcore.assets validate --manifest build/manifest.preview.json; echo $?
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
