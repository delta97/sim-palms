---
id: ASSET-004
title: "Smoke-test the asset pipeline end to end with a throwaway model"
status: todo
phase: 3
area: ASSET
kind: spike
plan_ref: "plans/detailed/03-palm-assets.md#w2-toolchain-and-pipeline-smoke-test"
depends_on: [ASSET-003, ASSET-008, SPIKE-003]
requires: [blender, windows-sim]
agent: asset-pipeline-artist
estimate_h: 5
touches: [assets/blender/_pipeline_test/, assets/TOOLCHAIN.md, tests/fixtures/palmcore/assets/sample_export/, plans/detailed/03-palm-assets.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Prove that a model goes from Blender through the 2024 exporter into a model-library package, loads in the sim, and can be placed by GUID with the scenery-object template palmgen will use. Capture real exporter output as test fixtures and answer the pipeline VERIFY items.

## Context

- This is the cheapest way to learn the exporter's actual behavior before anything real is modeled. Facts found here change the naming table, the GUID policy and the tooling (ASSET-007), so record them precisely.
- Follow `#w4-blender-scene-conventions` (origin at trunk base, meters, Z up, collection naming) for the test scene, so the fixtures look like real assets.
- The SPIKE-003 template for a scenery object is in `palmgen/templates/captured/`. Copy it into the throwaway project; don't edit it in place.
- The throwaway package lives under `build/pipeline-test/`, which is gitignored. Only the `.blend`, the captured fixtures and TOOLCHAIN.md are committed.
- The VERIFY items to answer are #2-#9 and #12 in `#open-questions-and-verify-items`.

## Steps

1. In `assets/blender/_pipeline_test/pipeline_test.blend`, build `palmfix_pipeline_test_medium`:
2. - LOD0: a 10 m tall 12-sided cylinder trunk with a base at z=0 extending to z=-0.15, plus 4 crossed quads at the top using an RGBA PNG with a cutout alpha.
3. - LOD1-3: reduced versions (8-, 6- and 4-sided, then crossed quads only).
4. - Material `mat_pipeline_test_fronds`: alpha mask, double-sided. Material `mat_pipeline_test_bark`: opaque.
5. Try the plugin's Auto LODs on a copy, and note how it's configured and what it outputs. Then export the hand-made LODs. Record every export setting you used under `## Export settings` in TOOLCHAIN.md.
6. Record what the exporter writes: file names per LOD, model XML structure, where the GUID lives and its format, the LOD switch attribute (for example `minSize`), and texture paths. Test whether a linked-duplicate frond and a geometry-nodes instance both export.
7. Create a throwaway package project in `build/pipeline-test/` with a model-library asset group pointing at a `modelLib/` folder that has a species subfolder. Record the asset group type name and whether subfolders are picked up. Build with `fspackagetool <project.xml> -outputdir <out> -nopause`.
8. Load the package in Dev Mode, find the model in the Scenery Editor object list, place one copy and check it at street level. Note whether it sits on the ground.
9. Copy SPIKE-003's scenery-object template, set its GUID to the test model's GUID, and include it in the throwaway project. Rebuild and confirm the object appears. Note whether the template supports scale, pitch and bank (lean).
10. Note how textures are converted (PNG to KTX2 during build?) and any size or power-of-two warnings from the build log.
11. Copy the exported model XML, all LOD `.gltf`/`.bin` files, one texture, the throwaway package definition XML and the project XML into `tests/fixtures/palmcore/assets/sample_export/`. Add a `README.md` there saying what each file is and which SDK and plugin versions produced it.
12. Write answers to VERIFY items #2-#9 and #12 under `## Findings` in TOOLCHAIN.md. If a finding contradicts the plan_ref (naming, GUID, folder layout), log it on this task and update the relevant table in `plans/detailed/03-palm-assets.md` in the same branch.

## Acceptance criteria

- [ ] The test model loads in the sim from a model-library package built with fspackagetool, with exit code 0.
- [ ] The test model appears when placed through a copy of the SPIKE-003 template with its GUID.
- [ ] `tests/fixtures/palmcore/assets/sample_export/` contains the real exporter output plus a README naming the versions.
- [ ] TOOLCHAIN.md has `## Export settings` and `## Findings` with answers (or 'unknown, because ...') for VERIFY #2-#9 and #12.

## Verification

On the sim PC:
```bat
fspackagetool build\pipeline-test\pipeline-test.xml -outputdir build\pipeline-test\out -nopause
echo %ERRORLEVEL%   & rem expect 0
```
Then in Dev Mode: load the package, open the Scenery Editor, and confirm both the hand-placed and the template-placed test models are visible at the test coordinate. Save one screenshot of each to the Log (paths only).

Anywhere:
```bash
ls tests/fixtures/palmcore/assets/sample_export/
grep -n '^## ' assets/TOOLCHAIN.md   # Versions, Install steps, Known issues, Export settings, Findings
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [integrator] Template path corrected to palmgen/templates/captured/ per plans/detailed/05-phases.md.
