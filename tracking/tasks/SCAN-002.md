---
id: SCAN-002
title: "Species normalization table, normalizer and palm filter"
status: in_progress
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w2-species-normalization-and-palm-filter"
depends_on: [SCAN-001]
requires: [none]
agent: geo-data-engineer
estimate_h: 3
touches: [palmscan/data/species_keys.yaml, palmscan/data/species_aliases.csv, palmscan/data/palm_genera.yaml, palmscan/data/species_defaults.yaml, palmscan/data/non_tree_markers.yaml, palmscan/species_names.py, palmscan/filters.py, tests/unit/palmscan/test_scan_species_names.py, tests/unit/palmscan/test_scan_filters.py]
owner: claude-agent
branch: task/scan-002-species-normalization-table-normalizer-a
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-002"
updated: 2026-11-22
---

## Goal

Any inventory or OSM species string maps to one internal species key (or "not a palm"), and stumps, vacant sites and removed trees are dropped. The name table is data (`palmscan/data/`), so new spellings are added without code changes.

## Context

- Spec: plan_ref section W2 (data file formats, seed lists, 9-step algorithm, test cases).
- Species keys match `plans/03-palm-assets.md#1-species-list` (`washingtonia_robusta`, ...). Non-modeled palms keep their real key (e.g. `phoenix_dactylifera`); mapping to models is palmgen's job.
- **Species key registry:** `palmscan/data/species_keys.yaml` is the one canonical list of valid species keys (species-level keys for every SoCal and Florida genus in W2, the `<genus>_sp` keys, and `palm_unknown`). The ARCH-002 schema keeps a pattern (`^[a-z]+(_[a-z]+)+$`); ASSET-005 validates manifest species keys against this file by path (palmcore must not import palmscan); normalization may only emit keys in it. Adding a species (DEC-006, DEC-011 Florida) means adding it here first.
- Watch the traps listed in the plan: `Cocos plumosa` is a queen palm, "sago palm" and "ponytail palm" are not palms, inventories write "PALM, MEXICAN FAN".
- SCAN-007 later extends the alias and marker tables from real recorded data; seed them broadly now.
- Package data files must be included in the wheel (check ARCH-001's packaging config; use `importlib.resources` to load them).

## Steps

0. Write `palmscan/data/species_keys.yaml`: `version: 1`, `keys:` a sorted list of `{key, genus, set: socal|florida|other, level: species|genus|generic}`; include `washingtonia_robusta`, `washingtonia_filifera`, `phoenix_canariensis`, `syagrus_romanzoffiana`, `archontophoenix_cunninghamiana`, the Florida keys `sabal_palmetto`, `roystonea_regia`, `cocos_nucifera`, `wodyetia_bifurcata`, every other species in the alias seed, every `<genus>_sp`, and `palm_unknown`.
1. Write `palmscan/data/palm_genera.yaml` (genus sets `socal`, `florida`, `genus_default_species`, `generic_palm_names`) as in the plan.
2. Write `palmscan/data/species_aliases.csv` (`alias,species_key,is_palm,notes`), sorted by alias, seeded with scientific names, synonyms and common names for every genus in the plan, plus the non-palm "palm" names.
3. Write `palmscan/data/species_defaults.yaml` (species rows, `_genus` rows for every genus, `_default`).
4. Write `palmscan/data/non_tree_markers.yaml` (`stump`, `vacant`, `removed` patterns).
5. `palmscan/species_names.py`: `NormalizedSpecies`, `clean_name`, `normalize_species(raw, common=None)` implementing steps 1-9; cached; tables loaded once via `importlib.resources`.
6. `palmscan/filters.py`: `non_tree_reason(species_raw, status_raw)` and `palm_filter(ns, genus_sets, exclude_species)` returning `None` or a reason (`not_palm`, `excluded_species`, `genus_not_in_set`).
7. Tests: every case listed in W2, plus a parametrized test that each alias row normalizes to its own key, and a check that the CSV is sorted and has no duplicate aliases. Registry tests: every `species_key` in the alias CSV, every `genus_default_species` value and every species row in `species_defaults.yaml` is in `species_keys.yaml`; every registry key matches the ARCH-002 schema pattern; keys are unique and sorted.

## Acceptance criteria

- [ ] `Washingtonia robusta`, `WASHINGTONIA ROBUSTA`, `Mexican fan palm` and `PALM, MEXICAN FAN` all give `washingtonia_robusta`, level `species`.
- [ ] `Cocos plumosa` gives `syagrus_romanzoffiana`; `Sago palm` gives `is_palm=False`.
- [ ] `Phoenix spp.` gives `phoenix_canariensis` level `genus`; `Brahea` gives `brahea_sp`; `Palm` gives `palm_unknown`.
- [ ] `Sabal palmetto` is filtered with `genus_not_in_set` when `genus_sets=[socal]` and kept with `[socal, florida]`.
- [ ] `Vacant Site` (species) and `STUMP` (status) return reasons `vacant` and `stump`.
- [ ] `palmscan/data/species_keys.yaml` exists and every key normalization can emit is in it.
- [ ] Every alias row round-trips; tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_species_names.py tests/unit/palmscan/test_scan_filters.py -q
python -c "from palmscan.species_names import normalize_species as n; print(n('PALM, MEXICAN FAN'), n('Cocos plumosa').key, n('Sago palm').is_palm)"
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Added the canonical species-key registry palmscan/data/species_keys.yaml (one list referenced by the ARCH-002 species pattern, SCAN normalization and ASSET-005 manifest validation) with tests tying the alias table, genus defaults and species_defaults to it. Cross-area reconciliation.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-002-species-normalization-table-normalizer-a worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-002
