---
id: ASSET-006
title: "glTF stats and automated asset checks (triangle budgets, heights, alpha mode, textures, naming)"
status: review
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w3-asset-tooling-in-python"
depends_on: [ASSET-005]
requires: [none]
agent: python-architect
estimate_h: 5
touches: [palmcore/assets/gltf_stats.py, palmcore/assets/checks.py, palmcore/assets/__main__.py, assets/budgets.yaml, tests/unit/palmcore/test_asset_checks.py, tests/fixtures/palmcore/assets/gltf/]
owner: claude-agent
branch: task/asset-006-gltf-stats-and-automated-asset-checks-tr
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ASSET-006"
updated: 2026-11-22
---

## Goal

`python -m palmcore.assets check` reads exported glTF and PNG files and enforces the budgets and rules in the plan_ref's check table, and `build-manifest` fills the measured fields (`native_height_m`, `crown_diam_m`, `lods[].triangles`) from glTF. Asset quality rules become code that runs anywhere.

## Context

- The check table, triangle math and bounding-box rules are in `#w3-asset-tooling-in-python`. Budget numbers come from `#w6-lods-and-budgets` and texture limits from `#w7-materials-and-textures`.
- Use only the standard library plus PyYAML. Parse `.gltf` as JSON. Read PNG width and height from the IHDR chunk (bytes 16-24, big-endian). Don't read `.bin` buffers: POSITION accessors carry `min`/`max` by the glTF 2.0 spec.
- Real exporter output may be `.glb` or `.gltf`. Support `.gltf` now and leave a clear error for `.glb` (ASSET-007 adds it if ASSET-004's sample needs it).
- Until ASSET-007 parses model XML, find LOD files by name: `<model_name>_LOD<n>.gltf` in the model folder.

## Steps

1. Write `assets/budgets.yaml` with `up_axis: y`; `lod_triangles` {0: {min: 3000, max: 6000}, 1: {min: 800, max: 1500}, 2: {min: 150, max: 300}, 3: {min: 0, max: 50}}; `florida_lod0_max: 3000`; `max_primitives` {default: 3, lod3: 1}; `height_tolerance` {lod0_vs_spec: 0.02, lod_vs_lod0: 0.03}; `base_z_range: [-0.25, 0.0]`; `crown_tolerance: 0.20`; `textures` max sizes per map role; `florida_texture_factor: 0.5`.
2. `palmcore/assets/gltf_stats.py`: `GltfStats` (triangles, primitives, bbox_min, bbox_max, materials with alphaMode/doubleSided, image URIs) and `read_gltf(path)`. Compose node transforms (TRS and `matrix`) down the scene hierarchy and transform all 8 bbox corners. Count triangles per mode (4: n/3; 5, 6: n-2; others: count 0 and warn).
3. `palmcore/assets/checks.py`: `CheckResult(level, check, subject, message)` and `run_checks(assets_dir, species=None) -> list[CheckResult]`, implementing every row of the check table except GUID (that's ASSET-007).
4. Extend `__main__.py` with `check [--species] [--assets-dir]`. Print an aligned table and a summary line `N errors, M warnings`. Exit 1 if there are any errors.
5. Plug `gltf_stats` into `build_manifest` as the default `measure` function, so measured fields come from LOD0/LOD0-3.
6. Fixtures in `tests/fixtures/palmcore/assets/gltf/`: hand-written minimal `.gltf` files (an embedded data-URI buffer is fine) covering indexed, non-indexed and strip primitives; a nested node with translation + scale; one BLEND material; a 2x2 PNG and a 3x2 PNG.
7. Tests in `tests/unit/palmcore/test_asset_checks.py`: triangle counts per mode, bbox through transforms, PNG size parsing, each check firing on a bad fixture and passing on a good one, and exit codes.

## Acceptance criteria

- [x] `pytest tests/unit/palmcore -q` passes.
- [x] Every row of the check table except GUID has at least one failing-fixture test.
- [x] Thresholds live only in `assets/budgets.yaml`. Changing a number there changes the check result with no code edit (covered by a test).
- [x] `build-manifest` on a fixture species with glTF fills the measured fields.

## Verification

```bash
pytest tests/unit/palmcore -q
python -m palmcore.assets check --assets-dir tests/fixtures/palmcore/assets/gltf; echo $?   # expect 1 (fixture dir includes bad cases)
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/asset-006-gltf-stats-and-automated-asset-checks-tr worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ASSET-006
- 2026-11-22 [claude-agent] Implemented gltf_stats.py, checks.py, budgets.yaml, check CLI, fixtures, 69 tests; build-manifest CLI now measures height/crown/triangles from LOD glTFs. pytest 564 passed 1 skipped (full), ruff check/format and mypy clean. Fixture dir check exits 1 (9 errors, 3 warnings). Commit 2d5139a
- 2026-11-22 [claude-agent] Status in_progress -> review.
