---
id: ASSET-030
title: "Canary Island date palm: species spec, textures and materials"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w10-other-socal-species"
depends_on: [ASSET-016]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 3
touches: [assets/species/phoenix_canariensis.yaml, assets/blender/phoenix_canariensis/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`phoenix_canariensis.blend` exists with scene conventions set up, the species spec yaml is written, and the textures, materials and master fronds are ready for LOD0 modeling (`ASSET-031`).

## Context

- The pipeline was proven on the Mexican fan palm (ASSET-010 to 016). Use `assets/blender/washingtonia_robusta/washingtonia_robusta.blend` as a template for scene setup, and read `assets/reviews/washingtonia_robusta.md` for lessons.
- Species features: Thick trunk with a diamond leaf-base pattern (albedo + normal), often a knob of leaf bases under the crown; large round crown of many long pinnate fronds.
- Notes: The crown is large (8-11 m) with 100+ fronds, so the LOD0 budget is tight. Use pinnate frond cards (alpha texture of leaflets on a bent strip of about 20-40 triangles) instead of modeled leaflets. The diamond leaf-base pattern is texture plus normal map, not geometry. Model the knob under the crown as a short bulged section of trunk.
- Conventions: `#w4-blender-scene-conventions`, `#naming-conventions`, `#w7-materials-and-textures`. Variants (`#w5-height-variants`): short 10 m (crown 8 m), medium 14 m (crown 10 m), tall 18 m (crown 11 m). Reference: `assets/reference/phoenix_canariensis.md`.
- Textures must be CC0 or self-made, and recorded in `assets/blender/phoenix_canariensis/textures/SOURCES.md`. Storage follows `assets/README.md`.
- If DEC-002 chose license or hybrid, replace modeling steps with 'import the licensed model, fix origin/scale/orientation to the conventions, rebuild materials to the W7 rules', and record the license terms and file source in `textures/SOURCES.md`.

## Steps

1. Optional: check the height distribution for `phoenix_canariensis` in any `palms.geojson` under `data/` (same one-liner as ASSET-010, with the species key swapped). Adjust the variant targets if needed and log the numbers.
2. Write `assets/species/phoenix_canariensis.yaml` with `status: draft`, `set: socal`, `lean_max_deg: 0`, and variants short/medium/tall.
3. Create `assets/blender/phoenix_canariensis/phoenix_canariensis.blend` with Metric units, scale 1.0, a collection tree per variant (`_LOD0`-`_LOD3`), and `_work` with reference images.
4. Make the textures within the W7 sizes: `tx_phoenix_canariensis_bark_albedo/normal/orm.png`, `tx_phoenix_canariensis_fronds_albedo/normal/orm.png`. Write SOURCES.md.
5. Create materials `mat_phoenix_canariensis_bark` and `mat_phoenix_canariensis_fronds`, plus any extra part materials from the notes, with the settings from TOOLCHAIN.md.
6. Model 1-3 master fronds in `_work` with UVs into the atlas.
7. Do a material test export to `build/phoenix_canariensis-mattest/` and run `python -m palmcore.assets check --assets-dir build/phoenix_canariensis-mattest`. The alpha and texture rows must have no ERROR.

## Acceptance criteria

- [ ] `assets/species/phoenix_canariensis.yaml` exists, with `status: draft`.
- [ ] The `.blend` follows the conventions. Textures are power-of-two, within size limits, and listed in SOURCES.md.
- [ ] The material test passes the alpha mode and texture checks.

## Verification

```bash
python -c "import yaml;d=yaml.safe_load(open('assets/species/phoenix_canariensis.yaml'));print(d['species'],[v['variant'] for v in d['variants']])"
python -m palmcore.assets check --assets-dir build/phoenix_canariensis-mattest
cat assets/blender/phoenix_canariensis/textures/SOURCES.md
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
