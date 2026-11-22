---
id: ASSET-071
title: "SimObject wrapper generator from the manifest (python -m palmcore.assets simobjects)"
status: todo
phase: 5
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w12-simobject-wrappers"
depends_on: [ASSET-070, ASSET-007]
requires: [none]
agent: python-architect
estimate_h: 4
touches: [palmcore/assets/simobjects.py, palmcore/assets/__main__.py, tests/unit/palmcore/test_asset_simobjects.py]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`python -m palmcore.assets simobjects --out DIR` writes one SimObject wrapper per manifest variant from the ASSET-070 templates, deterministically and with tests. Wrapper packages are then generated, never hand-made.

## Context

- Templates: `assets/simobjects/templates/`. Known-good instance: `tests/fixtures/palmcore/assets/simobject_sample/`. Layout and constraints: `assets/simobjects/README.md` (all from ASSET-070).
- Titles come from `simobject_title` in the manifest (always present by convention, `#manifest-contract`).
- If ASSET-070 found that wrappers need their own model copy, the generator also copies the model files from `assets/PackageSources/modelLib/` into the wrapper tree.

## Steps

1. `palmcore/assets/simobjects.py`: `render_wrapper(variant, templates_dir) -> dict[path, bytes]` and `write_wrappers(manifest, templates_dir, out_dir)`. Plain `str.replace` on the `{{...}}` placeholders, with an error on any leftover `{{`.
2. Add the `simobjects [--manifest] [--templates] --out` subcommand to `__main__.py`.
3. Tests: rendering the robusta medium variant reproduces the ASSET-070 sample byte for byte; leftover placeholders raise; output is deterministic; one wrapper is written per variant; titles are unique.

## Acceptance criteria

- [ ] `pytest tests/unit/palmcore/test_asset_simobjects.py -q` passes.
- [ ] Running against the committed manifest writes one wrapper per variant into `build/`.

## Verification

```bash
pytest tests/unit/palmcore/test_asset_simobjects.py -q
python -m palmcore.assets simobjects --out build/simobjects-test && find build/simobjects-test -maxdepth 3 | head
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
