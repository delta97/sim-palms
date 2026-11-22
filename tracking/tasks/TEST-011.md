---
id: TEST-011
title: Hand-label the false-positive site T4
status: todo
phase: 4
area: TEST
kind: test
plan_ref: "plans/detailed/06-testing.md#labeling-procedure"
depends_on: [TEST-009, TEST-100]
requires: [human]
agent: test-engineer
estimate_h: 2
touches: [tests/accuracy/T4/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Ground truth for T4 (Italian cypress, eucalyptus, light poles, few palms), so the false-positive rate of LiDAR detection can be measured as precision at T4.

## Context

- Procedure: `tests/accuracy/LABELING.md`. Label every palm in the area, even if there are only a handful.
- Also record non-palm look-alikes in `meta.yaml` `notes` (counts of cypress, poles), because those are what T4 tests. They are not features in `ground_truth.geojson`.
- Precision at T4 is the target; recall at T4 is not meaningful with few palms. Set `thresholds: {profiles: {lidar_only: {recall_min: null}, combined: {recall_min: null}}}` in `tests/accuracy/T4/meta.yaml`.

## Steps

1. `python -m tests.accuracy.gt init-site T4`.
2. Label all palms per LABELING.md. Fill `meta.yaml`, including the look-alike counts and the threshold override above.
3. `python -m tests.accuracy.gt validate T4`.

## Acceptance criteria

- [ ] T4 validates; every visible palm labeled.
- [ ] `meta.yaml` has look-alike counts and the recall override.

## Verification

```bash
python -m tests.accuracy.gt validate T4
grep -A3 thresholds tests/accuracy/T4/meta.yaml
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
