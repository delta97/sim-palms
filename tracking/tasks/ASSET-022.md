---
id: ASSET-022
title: "California fan palm: LOD1-LOD3, export and automated checks"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w6-lods-and-budgets"
depends_on: [ASSET-021]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 4
touches: [assets/blender/washingtonia_filifera/, assets/PackageSources/modelLib/washingtonia_filifera/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Every `washingtonia_filifera` variant has LOD1-LOD3 within budget, is exported into `assets/PackageSources/modelLib/washingtonia_filifera/`, and passes `python -m palmcore.assets check --species washingtonia_filifera` with 0 errors.

## Context

- LOD method, budgets and the cards bake: `#w6-lods-and-budgets`. Robusta's LODs (ASSET-013) are the worked example.
- Export settings: `assets/TOOLCHAIN.md`. Output layout: `#w8-export-and-packaging`.
- Don't write `assets/manifest.json` or the package definition (ASSET-100 integrates). Use the preview manifest in `build/`.

## Steps

1. Make LOD1 (Auto LODs, then hand-fix), LOD2 (cards, 6-sided trunk) and LOD3 (crossed quads with a baked silhouette) for each variant.
2. Bake `tx_washingtonia_filifera_cards_albedo.png` and add it to SOURCES.md.
3. Export each variant to `assets/PackageSources/modelLib/washingtonia_filifera/palmfix_washingtonia_filifera_<variant>/`, with textures in `assets/PackageSources/modelLib/washingtonia_filifera/texture/`. Run `stamp-guids --species washingtonia_filifera` if TOOLCHAIN.md says it's needed.
4. Run `python -m palmcore.assets check --species washingtonia_filifera` and fix every ERROR.
5. Run `python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json`, then `python -m palmcore.assets validate --manifest build/manifest.preview.json`. Leave the species at `status: draft`; the acceptance task sets the status.

## Acceptance criteria

- [ ] `8` LOD files exist under `assets/PackageSources/modelLib/washingtonia_filifera/`.
- [ ] `check --species washingtonia_filifera` exits 0.
- [ ] The preview manifest validates.

## Verification

```bash
python -m palmcore.assets check --species washingtonia_filifera; echo $?    # 0
python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json && python -m palmcore.assets validate --manifest build/manifest.preview.json; echo $?
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
