---
id: ASSET-050
title: "King palm: species spec, textures and materials"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w10-other-socal-species"
depends_on: [ASSET-016]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 3
touches: [assets/species/archontophoenix_cunninghamiana.yaml, assets/blender/archontophoenix_cunninghamiana/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`archontophoenix_cunninghamiana.blend` exists with scene conventions set up, the species spec yaml is written, and the textures, materials and master fronds are ready for LOD0 modeling (`ASSET-051`).

## Context

- The pipeline was proven on the Mexican fan palm (ASSET-010 to 016). Use `assets/blender/washingtonia_robusta/washingtonia_robusta.blend` as a template for scene setup, and read `assets/reviews/washingtonia_robusta.md` for lessons.
- Species features: Smooth ringed trunk (texture); green crownshaft (own material); arching pinnate fronds with leaflets that hang down.
- Notes: The bright green crownshaft between trunk and crown is the defining feature against queen palm. Give it its own material `mat_archontophoenix_cunninghamiana_crownshaft` and texture `tx_archontophoenix_cunninghamiana_crownshaft_albedo.png`. The trunk rings are texture. Fronds arch, and leaflets hang vertically from the rachis.
- Conventions: `#w4-blender-scene-conventions`, `#naming-conventions`, `#w7-materials-and-textures`. Variants (`#w5-height-variants`): short 10 m (crown 4.5 m), tall 14 m (crown 5.5 m). Reference: `assets/reference/archontophoenix_cunninghamiana.md`.
- Textures must be CC0 or self-made, and recorded in `assets/blender/archontophoenix_cunninghamiana/textures/SOURCES.md`. Storage follows `assets/README.md`.
- If DEC-002 chose license or hybrid, replace modeling steps with 'import the licensed model, fix origin/scale/orientation to the conventions, rebuild materials to the W7 rules', and record the license terms and file source in `textures/SOURCES.md`.

## Steps

1. Optional: check the height distribution for `archontophoenix_cunninghamiana` in any `palms.geojson` under `data/` (same one-liner as ASSET-010, with the species key swapped). Adjust the variant targets if needed and log the numbers.
2. Write `assets/species/archontophoenix_cunninghamiana.yaml` with `status: draft`, `set: socal`, `lean_max_deg: 0`, and variants short/tall.
3. Create `assets/blender/archontophoenix_cunninghamiana/archontophoenix_cunninghamiana.blend` with Metric units, scale 1.0, a collection tree per variant (`_LOD0`-`_LOD3`), and `_work` with reference images.
4. Make the textures within the W7 sizes: `tx_archontophoenix_cunninghamiana_bark_albedo/normal/orm.png`, `tx_archontophoenix_cunninghamiana_fronds_albedo/normal/orm.png`, `tx_archontophoenix_cunninghamiana_crownshaft_albedo.png`. Write SOURCES.md.
5. Create materials `mat_archontophoenix_cunninghamiana_bark` and `mat_archontophoenix_cunninghamiana_fronds`, plus any extra part materials from the notes, with the settings from TOOLCHAIN.md.
6. Model 1-3 master fronds in `_work` with UVs into the atlas.
7. Do a material test export to `build/archontophoenix_cunninghamiana-mattest/` and run `python -m palmcore.assets check --assets-dir build/archontophoenix_cunninghamiana-mattest`. The alpha and texture rows must have no ERROR.

## Acceptance criteria

- [ ] `assets/species/archontophoenix_cunninghamiana.yaml` exists, with `status: draft`.
- [ ] The `.blend` follows the conventions. Textures are power-of-two, within size limits, and listed in SOURCES.md.
- [ ] The material test passes the alpha mode and texture checks.

## Verification

```bash
python -c "import yaml;d=yaml.safe_load(open('assets/species/archontophoenix_cunninghamiana.yaml'));print(d['species'],[v['variant'] for v in d['variants']])"
python -m palmcore.assets check --assets-dir build/archontophoenix_cunninghamiana-mattest
cat assets/blender/archontophoenix_cunninghamiana/textures/SOURCES.md
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
