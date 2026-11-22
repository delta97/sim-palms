---
id: SCAN-009
title: "Palm sizes, exclusion radius, building conflict, mask_out"
status: todo
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w7-palm-attributes-and-exclusion"
depends_on: [SCAN-002]
requires: [none]
agent: geo-data-engineer
estimate_h: 3
touches: [palmscan/attributes.py, palmscan/mask.py, tests/unit/palmscan/test_scan_attributes.py, tests/unit/palmscan/test_scan_mask.py]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Every palm gets a height, crown diameter, clamped exclusion radius and `building_conflict` flag, and palms inside `mask_out` areas are removed with a logged reason.

## Context

- Spec: plan_ref section W7 and `plans/02-detection-pipeline.md` section 6.
- Inventories usually give DBH, which is not used for height. Phase 1 heights come from an inventory height field (if any) or `species_defaults.yaml`. `region_medians` is a Phase 4 input (SCAN-025) that this module must already accept.
- `exclusion_radius_m = crown_diam_m / 2 + exclusion.margin_m`, clamped to `[exclusion.radius_min_m, exclusion.radius_max_m]`. All three come from the region config `exclusion:` block (`RegionConfig.exclusion`, ARCH-003; defaults 1.5, 1.0, 8.0). Do not define defaults here. palmgen treats the written `exclusion_radius_m` as authoritative; its `--margin-m` tuning override recomputes from `crown_diam_m` with the same clamps.
- Masks: `RegionConfig.mask_out` items are `palmcore.config.MaskArea` (`name`, `kind` mod|airport|other, exactly one of `bbox`/`geometry`/`path`; paths already absolute, resolved against the repo root). Airport polygons from `masks.airports` are applied by palmgen, not here.
- Buildings come in as the GeoDataFrame from SCAN-006 (use a fixture frame in tests).

## Steps

1. `palmscan/attributes.py`: `parse_height(raw, units="ft")` (numbers, ranges, unit suffixes ft/'/m, class labels -> None); `assign_sizes(palms, cfg, region_medians=None)` with the order inventory -> region median -> species -> genus -> `_default`; skip palms whose `height_source == "lidar"`.
2. `assign_exclusion(palms, exclusion)` taking `RegionConfig.exclusion` (`margin_m`, `radius_min_m`, `radius_max_m`), with rounding to 0.01.
3. `flag_building_conflicts(palms, buildings, crs, overlap_min_m2=0.1)`: circles in local CRS, `STRtree` query, intersection area test; returns conflicting buildings (EPSG:4326, unique, sorted).
4. `palmscan/mask.py`: `load_masks(mask_out)` for `MaskArea` items with `bbox`, `geometry` or `path` (absolute); `apply_masks(palms, masks)` -> kept palms + rejects `stage="mask"`, `reason="mask_out:<name>"`.
5. Tests: height parsing table (`"35"`, `"30-45"`, `"10 m"`, `"40'"`, `"Large"`, `None`); out-of-range inventory height ignored; species/genus/default fallback; region median used when given; radius clamp at both ends (crown 0.5 m, margin 0 -> 1.0; crown 20 m -> 8.0); circle touching a building edge (overlap < 0.1 m2) is not a conflict, a 1 m overlap is; mask by bbox and by GeoJSON file.

## Acceptance criteria

- [ ] `parse_height("30-45", "ft")` returns 11.43 (+/- 0.01).
- [ ] A Canary Island date palm with crown 12 m and margin 1.5 gets radius 7.5; crown 20 m gets clamped to 8.0.
- [ ] Edge-touching circle is not flagged; overlapping circle is flagged and its building returned once.
- [ ] Masked palms appear as rejects with the mask name.
- [ ] Tests pass offline.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_attributes.py tests/unit/palmscan/test_scan_mask.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Exclusion margin and clamps now come from the region exclusion: block (ARCH-003 defaults margin 1.5, radius_min 1.0, radius_max 8.0); removed SCAN's duplicate 1.5 m min clamp. Masks use palmcore MaskArea (kind, bbox|geometry|path, absolute paths). Cross-area reconciliation.
