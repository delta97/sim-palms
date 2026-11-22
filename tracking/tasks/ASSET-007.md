---
id: ASSET-007
title: "Model XML parsing, GUID cross-check and LOD switch values in the manifest"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#guid-policy"
depends_on: [ASSET-006, ASSET-004]
requires: [none]
agent: python-architect
estimate_h: 4
touches: [palmcore/assets/model_xml.py, palmcore/assets/manifest.py, palmcore/assets/checks.py, palmcore/assets/__main__.py, tests/unit/palmcore/test_asset_model_xml.py, plans/detailed/03-palm-assets.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

The tooling understands the real 2024 exporter output captured in ASSET-004. It reads the GUID and LOD entries from the model XML, fails `validate`/`check` when a GUID doesn't match the manifest, fills `lods[].min_size`, and (only if needed) offers `stamp-guids`.

## Context

- Real sample files are in `tests/fixtures/palmcore/assets/sample_export/`, and the findings are in `assets/TOOLCHAIN.md` `## Findings` (both from ASSET-004). Base the parser on those files, not on assumptions about the format.
- GUID policy and format conversion: `#guid-policy`. The manifest stores lowercase without braces; convert to the exporter's format when comparing.
- If ASSET-004 found that the exporter writes LOD files under different names than `<model_name>_LOD<n>.gltf`, switch LOD discovery to the model XML's LOD list and update the naming table in the plan_ref.
- If ASSET-004 found `.glb` output, add `.glb` support to `gltf_stats.read_gltf` (JSON chunk only) and touch `palmcore/assets/gltf_stats.py` (add it to `touches` and log why).

## Steps

1. `palmcore/assets/model_xml.py`: `ModelXml(guid, lods=[(file, min_size)])` and `read_model_xml(path)`, using `xml.etree.ElementTree`, based on the captured sample.
2. In `manifest.py`, have `build_manifest` fill `lods[].file` and `lods[].min_size` from the model XML when it exists. `validate_manifest` adds: the model XML exists at `model_xml`, and its GUID equals the manifest GUID after normalization.
3. In `checks.py`, add the GUID row of the check table.
4. Only if TOOLCHAIN.md says the exporter can't take a fixed GUID: add `stamp-guids [--species]` to `__main__.py`, which rewrites the GUID in each model XML to the manifest value, in place and idempotently.
5. Tests in `tests/unit/palmcore/test_asset_model_xml.py`: parse the real sample, report a GUID mismatch, normalize GUIDs (braces, case), keep `stamp-guids` idempotent (if implemented), and extract min_size values.

## Acceptance criteria

- [ ] The parser works on the real ASSET-004 sample, with no hand-edited fixture standing in for it.
- [ ] A GUID mismatch makes both `validate` and `check` exit 1, with the model name in the message.
- [ ] `lods[].min_size` holds the exported values.
- [ ] `pytest tests/unit/palmcore -q` passes.

## Verification

```bash
pytest tests/unit/palmcore -q
pytest tests/unit/palmcore/test_asset_model_xml.py -q -k sample   # runs on the real ASSET-004 export
```
Expected: all pass. The GUID-mismatch test shows the model name in the error message.

## Log

- 2026-11-21 [plan-breakdown] Task created.
