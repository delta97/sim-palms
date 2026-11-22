---
id: SCAN-024
title: "Palm rule filter with reject reasons"
status: done
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w16-palm-rules"
depends_on: [SCAN-023]
requires: [none]
agent: lidar-analyst
estimate_h: 2
touches: [palmscan/detect/palm_rules.py, tests/unit/palmscan/test_scan_palm_rules.py]
owner: claude-agent
branch: task/scan-024-palm-rule-filter-with-reject-reasons
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-024"
updated: 2026-11-22
---

## Goal

`apply_palm_rules` marks each LiDAR candidate accepted or rejected using the source plan's palm test table, records every failing rule in order, and turns rejects into `Reject` rows for `qa_rejects.csv`.

## Context

- Spec: plan_ref section W16 (reason codes, thresholds, large-crown exemption, building check).
- The large-crown exemption is a deviation from the source plan (plan Q1), on by default and switchable via `rules.ratio_exempt_large_crown`.
- Buildings: the GeoDataFrame from SCAN-006 (fixture frame in tests), reprojected once to the local CRS.

## Steps

1. `RULE_ORDER` constant and one small predicate per rule.
2. `apply_palm_rules(cands, params, buildings_local)`: evaluate all rules, fill `reasons`, `accepted`; building test with buffered `STRtree` or `in_building`.
3. Rejects: `Reject(stage="lidar_rules", source="lidar", source_id=candidate_id, reason=reasons[0], all_reasons=reasons, metrics={height_m, crown_diam_m, ratio, shared_boundary_frac})`.
4. Parametrized tests: each threshold just inside/outside; exemption on/off for a 15 m / 9 m crown candidate; multiple failures in order; building buffer at 0.9 m vs 1.1 m.

## Acceptance criteria

- [x] Each rule boundary behaves as the table states.
- [x] A 15 m tall, 9 m crown, isolated candidate passes with the exemption and fails `ratio` without it.
- [x] Reject rows carry all metrics needed by `qa_rejects.csv`.
- [x] Tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_palm_rules.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-024-palm-rule-filter-with-reject-reasons worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-024
- 2026-11-22 [claude-agent] Implemented palm_rules.py + tests; full suite 1655 passed, 5 skipped; ruff/format/mypy clean; all acceptance boxes pass
- 2026-11-22 [claude-agent] Status in_progress -> review.
- 2026-11-22 [integrator] Status review -> done.
