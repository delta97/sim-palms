---
id: REGION-021
title: "LA Westside and beaches: add mask_out areas for other mods and airports"
status: todo
phase: 6
area: REGION
kind: build
plan_ref: "plans/detailed/05-phases.md#per-region-task-pattern"
depends_on: [REGION-020, RISK-003, RISK-004]
requires: [network, human]
agent: geo-data-engineer
estimate_h: 1
touches: [regions/la-westside.yaml]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

`regions/la-westside.yaml` masks out every area where another installed mod or an airport add-on already handles trees, so the fix never doubles palms or cuts airport scenery (R-13).

## Context

- Pattern and order: `plans/detailed/05-phases.md#per-region-task-pattern`. Commands: `docs/regions/RUNBOOK.md` (REGION-001).
- Region: **LA Westside and beaches**, file `regions/la-westside.yaml`, `id_prefix: law` (ARCH-008 wrote the starting file).
- If this region was the Phase 1-5 test region (it contains the DEC-004 block), most of this step was done before: review and update instead of starting over, and say so in the Log.
- If DEC-011 (ADR-0012) drops or reorders this region, set this task to `dropped` or adjust `depends_on`, and log why.
- Candidate masks: `docs/compat/mods-coverage.geojson` (RISK-003) and `docs/compat/airports-mask.geojson` (RISK-004). They are candidates, not config: copy only what applies.
- Airports: `masks.airports.enabled: true` (default) makes `palmgen masks airports` fetch aerodrome outlines from OSM. Add explicit `mask_out` entries (`kind: airport`) only for add-on airports whose scenery reaches beyond the OSM outline. Santa Monica (KSMO) is inside the bbox and Los Angeles International (KLAX) is just south of it; check whether the airport buffer reaches into the bbox (VERIFY against `docs/compat/airports.md`).
- Mods: The Los Angeles palm enhancement mod (flightsim.to addon 81258) covers LA palms. If the user runs it, mask its coverage area out, or the user stops running it here (R-13). Check `docs/compat/other-mods.md`.
- Mask item format: `name`, `kind` (`mod`, `airport`, `other`), one of `bbox`, `geometry` or `path`, optional `note` (`plans/detailed/01-architecture.md#ws7-region-config`). Relative paths resolve against the repo root.

## Steps

1. Ask the user which mods and airport add-ons in their Community folder cover this region (list them in the Log).
2. For each one that overlaps the bbox, add a `mask_out` entry. Prefer `path:` pointing at a GeoJSON under `docs/compat/` over pasting coordinates; use `note:` for the mod name and version.
3. Run `palmgen masks airports --region la-westside` (network). Record how many airport polygons it wrote.
4. Load the region bbox, the `mask_out` areas and the airport file in QGIS over aerial imagery; screenshot into the Log (or describe). Confirm with the user that nothing important is masked by mistake.
5. Validate with `check_regions` as in REGION-020.

## Acceptance criteria

- [ ] Every installed overlapping mod or add-on has a `mask_out` entry, or the Log says why not.
- [ ] `palmgen masks airports --region la-westside` ran and its polygon count is logged.
- [ ] The user confirmed the mask map.

## Verification

```bash
grep -nA3 "mask_out" regions/la-westside.yaml
python -c "from pathlib import Path; from palmcore.config import check_regions; print(check_regions(Path('regions')))"
```

## Log

- 2026-11-22 [plan-breakdown] Task created.
