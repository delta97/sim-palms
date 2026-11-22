---
id: REGION-020
title: "LA Westside and beaches: finalise the region YAML (bbox, sources, settings, no overlaps)"
status: todo
phase: 6
area: REGION
kind: build
plan_ref: "plans/detailed/05-phases.md#per-region-task-pattern"
depends_on: [REGION-001, DEC-011, ARCH-008]
requires: [network]
agent: geo-data-engineer
estimate_h: 1
touches: [regions/la-westside.yaml]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

`regions/la-westside.yaml` is ready for a full-region run: bbox covers the photogrammetry area the user flies, sources are verified and current, exclusion settings carry the values tuned in Phase 2, and the bbox does not overlap another region.

## Context

- Pattern and order: `plans/detailed/05-phases.md#per-region-task-pattern`. Commands: `docs/regions/RUNBOOK.md` (REGION-001).
- Region: **LA Westside and beaches**, file `regions/la-westside.yaml`, `id_prefix: law` (ARCH-008 wrote the starting file).
- If this region was the Phase 1-5 test region (it contains the DEC-004 block), most of this step was done before: review and update instead of starting over, and say so in the Log.
- If DEC-011 (ADR-0012) drops or reorders this region, set this task to `dropped` or adjust `depends_on`, and log why.
- Inventory: the LA County compilation (stiles/la-trees) and StreetsLA if it has an endpoint (ARCH-008 log). Building source: ADR-0010. LiDAR: `3dep_ept`.
- Overlapping regions place two palms for one tree (plan 01 Q7). Regions must not overlap, or must `mask_out` each other.
- Species priors stay as they are here; REGION-022 computes real ones.

## Steps

1. Open `regions/la-westside.yaml`. Compare its bbox with the area the user wants covered (ADR-0012) and with photogrammetry coverage (ask the user to confirm the edges in the sim, or use the DEC-011 evidence). Adjust the bbox if needed.
2. Re-check each inventory source: endpoint reachable, field names unchanged, latest edit date (record as `vintage`). Use the ArcGIS `?f=pjson` metadata or the file's commit date; don't download whole datasets here.
3. Copy the tuned exclusion values from the test region YAML (`exclusion.margin_m`, `clip_buffer_m`, set in GEN-017) unless this is the test region.
4. Check for overlap with every other `regions/*.yaml` bbox (one-liner in RUNBOOK.md). If they overlap, shrink one bbox or add a `mask_out` entry `kind: other` covering the other region, and note which.
5. Validate: `python -c "from pathlib import Path; from palmcore.config import check_regions; print(check_regions(Path('regions')))"` prints `[]`.

## Acceptance criteria

- [ ] `check_regions` returns `[]` and `pytest tests/unit/palmcore/test_region_files.py -q` passes.
- [ ] Every inventory source has a `vintage` and a date-checked note in the Log.
- [ ] No bbox overlap with another region, or a `mask_out` entry covers it.

## Verification

```bash
python -c "from pathlib import Path; from palmcore.config import check_regions; print(check_regions(Path('regions')))"
pytest tests/unit/palmcore/test_region_files.py -q
grep -nE "bbox|vintage|margin_m" regions/la-westside.yaml
```

## Log

- 2026-11-22 [plan-breakdown] Task created.
