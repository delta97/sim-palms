---
id: ASSET-032
title: "Canary Island date palm: LOD1-LOD3, export and automated checks"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w6-lods-and-budgets"
depends_on: [ASSET-031]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 4
touches: [assets/blender/phoenix_canariensis/, assets/PackageSources/modelLib/phoenix_canariensis/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Every `phoenix_canariensis` variant has LOD1-LOD3 within budget, is exported into `assets/PackageSources/modelLib/phoenix_canariensis/`, and passes `python -m palmcore.assets check --species phoenix_canariensis` with 0 errors.

## Context

- LOD method, budgets and the cards bake: `#w6-lods-and-budgets`. Robusta's LODs (ASSET-013) are the worked example.
- Export settings: `assets/TOOLCHAIN.md`. Output layout: `#w8-export-and-packaging`.
- Don't write `assets/manifest.json` or the package definition (ASSET-100 integrates). Use the preview manifest in `build/`.

## Steps

1. Make LOD1 (Auto LODs, then hand-fix), LOD2 (cards, 6-sided trunk) and LOD3 (crossed quads with a baked silhouette) for each variant.
2. Bake `tx_phoenix_canariensis_cards_albedo.png` and add it to SOURCES.md.
3. Export each variant to `assets/PackageSources/modelLib/phoenix_canariensis/palmfix_phoenix_canariensis_<variant>/`, with textures in `assets/PackageSources/modelLib/phoenix_canariensis/texture/`. Run `stamp-guids --species phoenix_canariensis` if TOOLCHAIN.md says it's needed.
4. Run `python -m palmcore.assets check --species phoenix_canariensis` and fix every ERROR.
5. Run `python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json`, then `python -m palmcore.assets validate --manifest build/manifest.preview.json`. Leave the species at `status: draft`; the acceptance task sets the status.

## Acceptance criteria

- [ ] `12` LOD files exist under `assets/PackageSources/modelLib/phoenix_canariensis/`.
- [ ] `check --species phoenix_canariensis` exits 0.
- [ ] The preview manifest validates.

## Verification

```bash
python -m palmcore.assets check --species phoenix_canariensis; echo $?    # 0
python -m palmcore.assets build-manifest --include-draft --out build/manifest.preview.json && python -m palmcore.assets validate --manifest build/manifest.preview.json; echo $?
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
