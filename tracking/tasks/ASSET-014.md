---
id: ASSET-014
title: "Mexican fan palm: export, create the palmfix-assets package, generate the first manifest"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w8-export-and-packaging"
depends_on: [ASSET-013, ASSET-007]
requires: [blender, windows-sim]
agent: asset-pipeline-artist
estimate_h: 4
touches: [assets/PackageSources/modelLib/washingtonia_robusta/, assets/species/washingtonia_robusta.yaml, assets/palmfix-assets.xml, assets/PackageDefinitions/palmfix-assets.xml, assets/manifest.json, assets/library.yaml]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

The robusta variants are exported into `assets/PackageSources/modelLib/washingtonia_robusta/`, the `palmfix-assets` package project exists and builds with fspackagetool, and the committed `assets/manifest.json` lists robusta (`status: in_review`) so GEN can place it.

## Context

- Export and packaging rules: `#w8-export-and-packaging`. Package structure (asset group type, folder): copy it from the throwaway project captured in ASSET-004 (`tests/fixtures/palmcore/assets/sample_export/`).
- GUIDs follow `#guid-policy`. If the exporter can't take a fixed GUID, run `python -m palmcore.assets stamp-guids --species washingtonia_robusta` after export.
- VERIFY #12: how a region package declares a dependency on `palmfix-assets`. Look it up while making the package definition and log the finding for GEN.
- This is the first task that writes the committed `assets/manifest.json`.

## Steps

1. Export each variant with the TOOLCHAIN.md settings to `assets/PackageSources/modelLib/washingtonia_robusta/palmfix_washingtonia_robusta_<variant>/`, with textures in `assets/PackageSources/modelLib/washingtonia_robusta/texture/`.
2. Run `python -m palmcore.assets stamp-guids --species washingtonia_robusta` if it applies.
3. Create `assets/palmfix-assets.xml` (project) and `assets/PackageDefinitions/palmfix-assets.xml` (definition) with a model-library asset group pointing at `PackageSources/modelLib/`, at version 0.1.0 (matching `assets/library.yaml`).
4. Set `status: in_review` in `assets/species/washingtonia_robusta.yaml`.
5. Run `python -m palmcore.assets check --species washingtonia_robusta`. It must show 0 errors.
6. Run `python -m palmcore.assets build-manifest`, then `python -m palmcore.assets validate`.
7. On the sim PC, build: `fspackagetool assets\palmfix-assets.xml -outputdir build\palmfix-assets -nopause`. Then confirm the build log has no errors for any of the 3 models.
8. In Dev Mode, confirm all 3 models appear in the Scenery Editor object list. Note the GUIDs shown and compare them with the manifest.
9. Log the dependency-declaration finding (VERIFY #12) for GEN.

## Acceptance criteria

- [ ] fspackagetool exits 0, and the build output contains the 3 robusta models.
- [ ] `assets/manifest.json` contains robusta with 3 variants, measured heights and triangles. `validate` exits 0.
- [ ] `build-manifest --check` exits 0 (the committed file is current).
- [ ] The GUIDs shown in the sim match the manifest.

## Verification

```bash
python -m palmcore.assets check --species washingtonia_robusta; echo $?        # 0
python -m palmcore.assets build-manifest --check; echo $?        # 0
python -m palmcore.assets validate; echo $?                      # 0
```
On the sim PC:
```bat
fspackagetool assets\palmfix-assets.xml -outputdir build\palmfix-assets -nopause
echo %ERRORLEVEL%   & rem 0
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
