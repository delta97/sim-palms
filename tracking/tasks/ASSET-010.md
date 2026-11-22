---
id: ASSET-010
title: "Mexican fan palm: species spec, textures and materials"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w9-mexican-fan-palm-first"
depends_on: [GATE-P2, ASSET-001, ASSET-004, ASSET-005]
requires: [blender]
agent: asset-pipeline-artist
estimate_h: 4
touches: [assets/species/washingtonia_robusta.yaml, assets/blender/washingtonia_robusta/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

`washingtonia_robusta.blend` exists with scene conventions set up, the species spec yaml is written, and the bark, frond and (optional) skirt textures and materials are done. LOD0 modeling (ASSET-011) can then focus on geometry.

## Context

- This is the first real species. It proves the pipeline before the other four (`#w9-mexican-fan-palm-first`).
- Conventions: `#w4-blender-scene-conventions`, `#naming-conventions`, `#w7-materials-and-textures`. Variant heights: `#w5-height-variants`. Reference: `assets/reference/washingtonia_robusta.md` (ASSET-001).
- Exporter facts (material type, alpha settings, texture rules) are in `assets/TOOLCHAIN.md` `## Findings` (ASSET-004).
- Storage: follow the policy decided in DEC-008 (ADR-0009) and applied by ASSET-008 (`assets/README.md`) for the `.blend` and PNGs.
- Pilot: this species is the pilot run under DEC-002's provisional default (build one species first). Log hours per step; DEC-002 uses them.
- Textures must be CC0 or self-made. Record each one's source in `assets/blender/washingtonia_robusta/textures/SOURCES.md`.
- If DEC-002 has already been decided as license or hybrid when this task starts, replace modeling steps with 'import the licensed model, fix origin/scale/orientation to the conventions, rebuild materials to the W7 rules', and record the license terms and file source in `textures/SOURCES.md`.

## Steps

1. Optional but recommended: if any `build/scan/<region>/palms.geojson` exists (canonical palmscan output, from SCAN-100), print the height distribution for this species: `python -c "import json,sys,statistics as s; f=json.load(open(sys.argv[1]))['features']; h=sorted(x['properties']['height_m'] for x in f if x['properties']['species']=='washingtonia_robusta' and x['properties'].get('height_m')); print(len(h), h[len(h)//10], s.median(h), h[9*len(h)//10])" <path>`. Adjust the W5 target heights if the 10th to 90th percentile range is poorly covered, and log the numbers.
2. Write `assets/species/washingtonia_robusta.yaml` in the format shown in `#manifest-contract`, with `status: draft`, `set: socal`, `lean_max_deg: 5`, and variants short/medium/tall.
3. Create `assets/blender/washingtonia_robusta/washingtonia_robusta.blend`: Metric, unit scale 1.0, collections `palmfix_washingtonia_robusta_<variant>` with `_LOD0`-`_LOD3` children, plus `_work`. Add reference images from ASSET-001 in `_work`.
4. Make the textures in `assets/blender/washingtonia_robusta/textures/`, sized within the W7 table: `tx_washingtonia_robusta_bark_albedo/normal/orm.png`, `tx_washingtonia_robusta_fronds_albedo.png` (RGBA fan-leaf atlas with 2-4 fan shapes, including a dead brown frond for the skirt), `tx_washingtonia_robusta_fronds_normal.png`, `tx_washingtonia_robusta_fronds_orm.png`. Write `SOURCES.md` covering every file.
5. Create the materials `mat_washingtonia_robusta_bark` (opaque), `mat_washingtonia_robusta_fronds` (alpha mask, cutoff 0.5, double-sided), and `mat_washingtonia_robusta_skirt` if the skirt uses its own texture. Use the MSFS material settings recorded in TOOLCHAIN.md.
6. Model 2-3 master fan fronds (live, drooping, dead) in `_work` with UVs into the atlas, each around 100-200 triangles.
7. Do a quick material test: export one master frond on a stub trunk with the recorded settings into `build/robusta-mattest/`, and run `python -m palmcore.assets check --assets-dir build/robusta-mattest` to confirm the alpha mode and texture checks pass. Don't commit these exports.

## Acceptance criteria

- [ ] `assets/species/washingtonia_robusta.yaml` exists and loads with `python -c "import yaml;print(yaml.safe_load(open('assets/species/washingtonia_robusta.yaml')))"`.
- [ ] The `.blend` follows the collection, unit and origin conventions.
- [ ] Every texture is power-of-two, within its W7 size, and listed in SOURCES.md with a CC0 or self-made source.
- [ ] The material test export passes the alpha mode and texture checks.

## Verification

```bash
python -c "import yaml;d=yaml.safe_load(open('assets/species/washingtonia_robusta.yaml'));print(d['species'],[v['variant'] for v in d['variants']])"
python -m palmcore.assets check --assets-dir build/robusta-mattest   # alpha/texture rows: no ERROR
cat assets/blender/washingtonia_robusta/textures/SOURCES.md
```
In Blender: Scene Properties > Units shows Metric and 1.0, and the Outliner shows the collection tree.

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Removed depends_on DEC-002: this is the Mexican fan palm pilot, which runs under DEC-002's provisional default ('build one species first'); DEC-002 is now needed before modeling beyond the pilot (ASSET-016 depends on it). Storage policy reference updated to DEC-008/ASSET-008. Cross-area reconciliation.
- 2026-11-22 [reconcile] Height-distribution check now points at the canonical palmscan output build/scan/<region>/palms.geojson instead of data/ (data/ is the download cache). Cross-area reconciliation.
- 2026-11-22 [integrator] integrator note from ASSET-001: some proportions in assets/reference/*.md are VERIFY (no published source) — measure from the linked reference photos; ASSET-001 also flags plan W5 crown widths for robusta/filifera as above extension figures
