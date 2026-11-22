---
id: TEST-101
title: Hand-label ground-truth palms at T1 and T2 (about 200 palms)
status: todo
phase: 4
area: TEST
kind: test
plan_ref: "plans/detailed/06-testing.md#labeling-procedure"
depends_on: [TEST-009, TEST-100]
requires: [human]
agent: test-engineer
estimate_h: 6
touches: [tests/accuracy/T1/, tests/accuracy/T2/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`tests/accuracy/T1/` and `tests/accuracy/T2/` hold validated, hand-labeled ground truth (about 100 palms each) so detection precision, recall and position error can be measured.

## Context

- Procedure: `tests/accuracy/LABELING.md` (TEST-009). Format: `plans/detailed/06-testing.md#ground-truth-format`.
- T1 is the inventory street (happy path); T2 the beach site (LiDAR only). Sites and bboxes: `tests/sites/sites.yaml` (TEST-100).
- This needs no sim and no palmscan output. Doing T1 early (before Phase 4) lets the Phase 1 gate use the `phase1_inventory` metric profile.
- Don't look at palmscan predictions while labeling. Label what the imagery shows.
- If a site has far more than 100 palms, shrink `labeled_area.geojson` to a sub-area with about 100 and note it in `meta.yaml`. If far fewer, enlarge it within the site bbox.

## Steps

1. `python -m tests.accuracy.gt init-site T1` (and T2).
2. Follow LABELING.md in QGIS for T1. Fill `meta.yaml` (imagery source and date, labeler, date).
3. `python -m tests.accuracy.gt validate T1`. Fix errors.
4. Repeat for T2.
5. If a palmscan CHM exists, run `fill-heights` for both sites; otherwise leave `height_ref_m` null and note "fill-heights pending" in the Log (TEST-012 does it).
6. Spot-check: pick 10 random labels per site and re-check them on the imagery; note how many you changed in `meta.yaml` `notes`.

## Acceptance criteria

- [ ] Both sites validate.
- [ ] About 200 labels in total (at least 150), with `meta.yaml` complete.
- [ ] Spot-check result recorded.

## Verification

```bash
python -m tests.accuracy.gt validate T1
python -m tests.accuracy.gt validate T2
python -c "import json; print(sum(len(json.load(open(f'tests/accuracy/{s}/ground_truth.geojson'))['features']) for s in ('T1','T2')))"   # >= 150
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-21 [plan-breakdown] Task created.
