---
id: ASSET-100
title: "Deliverable: palmfix-assets 1.0.0 model library package with GUID/variant manifest"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w8-export-and-packaging"
depends_on: [ASSET-016, ASSET-023, ASSET-033, ASSET-043, ASSET-053]
requires: [windows-sim]
agent: asset-pipeline-artist
estimate_h: 3
touches: [assets/manifest.json, assets/library.yaml, assets/PackageDefinitions/palmfix-assets.xml, assets/README.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`palmfix-assets` 1.0.0 builds with fspackagetool and contains all 12 SoCal variants. The committed `assets/manifest.json` lists all 5 species as `accepted`, and GEN can load it. This is the Phase 3 asset deliverable that region packages depend on.

## Context

- This is an anchor that other areas depend on (GEN variant selection, GATE-P3, LIVE via ASSET-101, Florida via ASSET-060). Keep the id.
- The contract GEN consumes: `#manifest-contract` and `#what-gen-and-live-consume`.
- Species tasks wrote exports and set `status: accepted` but didn't touch the manifest or package definition. This task integrates them.
- Version: 1.0.0 (`#w8-export-and-packaging`). Bump it in `assets/library.yaml` and the package definition together.

## Steps

1. Confirm that all 5 species yamls have `status: accepted`: `grep -L 'status: accepted' assets/species/*.yaml` prints nothing.
2. Set `species_fallback` in `assets/library.yaml`. Remove the SoCal entries (all have models now), add the Florida fallbacks from `#w13-florida-set`, and keep `_default`.
3. Set `package_version: 1.0.0` in `assets/library.yaml` and in `assets/PackageDefinitions/palmfix-assets.xml`.
4. Run `python -m palmcore.assets check` (all species), `build-manifest`, and `validate`.
5. On the sim PC: `fspackagetool assets\palmfix-assets.xml -outputdir build\palmfix-assets -nopause`. Confirm the build log has no errors and the output contains 12 models.
6. In Dev Mode, spot-check one variant per species in the Scenery Editor list.
7. Smoke-test the consumer path: `python -c "from palmcore.assets.manifest import load_manifest as l; m=l('assets/manifest.json'); print({k: len(s.variants) for k, s in m.species.items()})"` prints 5 species and 12 variants.
8. Update `assets/README.md` with the current version and the species/variant table.
9. Log the package version and the manifest's git blob hash (`git hash-object assets/manifest.json`) so GEN can reference them.

## Acceptance criteria

- [ ] fspackagetool exits 0, and the output has 12 models.
- [ ] The manifest has 5 accepted species and 12 variants. `validate` and `build-manifest --check` exit 0.
- [ ] `package_version` is 1.0.0 in the manifest, library.yaml and the package definition.
- [ ] The `load_manifest` smoke test prints the expected counts.

## Verification

```bash
python -m palmcore.assets check; echo $?                 # 0
python -m palmcore.assets build-manifest --check; echo $? # 0
python -m palmcore.assets validate; echo $?               # 0
python -c "from palmcore.assets.manifest import load_manifest as l; m=l('assets/manifest.json'); print(m.package_version, sum(len(s.variants) for s in m.species.values()))"   # 1.0.0 12
```
On the sim PC:
```bat
fspackagetool assets\palmfix-assets.xml -outputdir build\palmfix-assets -nopause
echo %ERRORLEVEL%   & rem 0
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
