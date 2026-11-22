---
id: ASSET-020
title: "California fan palm: species spec, textures and materials"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w10-other-socal-species"
depends_on: [ASSET-016]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 3
touches: [assets/species/washingtonia_filifera.yaml, assets/blender/washingtonia_filifera/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`washingtonia_filifera.blend` exists with scene conventions set up, the species spec yaml is written, and the textures, materials and master fronds are ready for LOD0 modeling (`ASSET-021`).

## Context

- The pipeline was proven on the Mexican fan palm (ASSET-010 to 016). Use `assets/blender/washingtonia_robusta/washingtonia_robusta.blend` as a template for scene setup, and read `assets/reviews/washingtonia_robusta.md` for lessons.
- Species features: Thick columnar trunk; heavy full-length or half skirt of dead fronds (shell mesh with an alpha-tested texture); larger, greyer-green fans than robusta.
- Notes: The skirt is the defining feature. Model it as 1-2 tapered shell meshes around the trunk using `tx_washingtonia_filifera_skirt_albedo.png` (alpha mask, double-sided), not as individual dead fronds. Reuse robusta's fan frond topology as the starting point, but make the fans larger and greyer. Check against `## Look-alikes` so it doesn't end up as a fat robusta.
- Conventions: `#w4-blender-scene-conventions`, `#naming-conventions`, `#w7-materials-and-textures`. Variants (`#w5-height-variants`): short 12 m (crown 4.5 m), tall 16 m (crown 5.5 m). Reference: `assets/reference/washingtonia_filifera.md`.
- Textures must be CC0 or self-made, and recorded in `assets/blender/washingtonia_filifera/textures/SOURCES.md`. Storage follows `assets/README.md`.
- If DEC-002 chose license or hybrid, replace modeling steps with 'import the licensed model, fix origin/scale/orientation to the conventions, rebuild materials to the W7 rules', and record the license terms and file source in `textures/SOURCES.md`.

## Steps

1. Optional: check the height distribution for `washingtonia_filifera` in any `palms.geojson` under `data/` (same one-liner as ASSET-010, with the species key swapped). Adjust the variant targets if needed and log the numbers.
2. Write `assets/species/washingtonia_filifera.yaml` with `status: draft`, `set: socal`, `lean_max_deg: 3`, and variants short/tall.
3. Create `assets/blender/washingtonia_filifera/washingtonia_filifera.blend` with Metric units, scale 1.0, a collection tree per variant (`_LOD0`-`_LOD3`), and `_work` with reference images.
4. Make the textures within the W7 sizes: `tx_washingtonia_filifera_bark_albedo/normal/orm.png`, `tx_washingtonia_filifera_fronds_albedo/normal/orm.png`, `tx_washingtonia_filifera_skirt_albedo.png`. Write SOURCES.md.
5. Create materials `mat_washingtonia_filifera_bark` and `mat_washingtonia_filifera_fronds`, plus any extra part materials from the notes, with the settings from TOOLCHAIN.md.
6. Model 1-3 master fronds in `_work` with UVs into the atlas.
7. Do a material test export to `build/washingtonia_filifera-mattest/` and run `python -m palmcore.assets check --assets-dir build/washingtonia_filifera-mattest`. The alpha and texture rows must have no ERROR.

## Acceptance criteria

- [ ] `assets/species/washingtonia_filifera.yaml` exists, with `status: draft`.
- [ ] The `.blend` follows the conventions. Textures are power-of-two, within size limits, and listed in SOURCES.md.
- [ ] The material test passes the alpha mode and texture checks.

## Verification

```bash
python -c "import yaml;d=yaml.safe_load(open('assets/species/washingtonia_filifera.yaml'));print(d['species'],[v['variant'] for v in d['variants']])"
python -m palmcore.assets check --assets-dir build/washingtonia_filifera-mattest
cat assets/blender/washingtonia_filifera/textures/SOURCES.md
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
