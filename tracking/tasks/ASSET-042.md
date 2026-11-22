---
id: ASSET-042
title: "Queen palm: LOD1-LOD3, export and automated checks"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w6-lods-and-budgets"
depends_on: [ASSET-041]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 4
touches: [assets/blender/syagrus_romanzoffiana/, assets/PackageSources/modelLib/syagrus_romanzoffiana/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Every `syagrus_romanzoffiana` variant has LOD1-LOD3 within budget, is exported into `assets/PackageSources/modelLib/syagrus_romanzoffiana/`, and passes `python -m palmcore.assets check --species syagrus_romanzoffiana` with 0 errors.

## Context

- LOD method, budgets and the cards bake: `#w6-lods-and-budgets`. Robusta's LODs (ASSET-013) are the worked example.
- Export settings: `assets/TOOLCHAIN.md`. Output layout: `#w8-export-and-packaging`.
- Don't write `assets/manifest.json` or the package definition (ASSET-100 integrates). Use the preview manifest in `build/`.

## Steps

1. Make LOD1 (Auto LODs, then hand-fix), LOD2 (cards, 6-sided trunk) and LOD3 (crossed quads with a baked silhouette) for each variant.
2. Bake `tx_syagrus_romanzoffiana_cards_albedo.png` and add it to SOURCES.md.
3. Export each variant to `assets/PackageSources/modelLib/syagrus_romanzoffiana/palmfix_syagrus_romanzoffiana_<variant>/`, with textures in `assets/PackageSources/modelLib/syagrus_romanzoffiana/texture/`. Run `stamp-guids --species syagrus_romanzoffiana` if TOOLCHAIN.md says it's needed.
4. Run `python -m palmcore.assets check --species syagrus_romanzoffiana` and fix every ERROR.
5. Run `python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json`, then `python -m palmcore.assets validate --manifest build/manifest.preview.json`. Leave the species at `status: draft`; the acceptance task sets the status.

## Acceptance criteria

- [ ] `8` LOD files exist under `assets/PackageSources/modelLib/syagrus_romanzoffiana/`.
- [ ] `check --species syagrus_romanzoffiana` exits 0.
- [ ] The preview manifest validates.

## Verification

```bash
python -m palmcore.assets check --species syagrus_romanzoffiana; echo $?    # 0
python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json && python -m palmcore.assets validate --manifest build/manifest.preview.json; echo $?
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
