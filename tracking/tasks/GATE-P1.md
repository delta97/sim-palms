---
id: GATE-P1
title: "Phase 1 exit gate: palms.geojson for the test neighbourhood from inventory data"
status: todo
phase: 1
area: GATE
kind: gate
plan_ref: "plans/detailed/05-phases.md#phase-1-detection-mvp"
depends_on: [GATE-P0, ARCH-008, DEC-009, TEST-004, TEST-100, SCAN-100]
requires: [human]
agent: task-planner
estimate_h: 0.5
touches: []
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

The user confirms that `palmscan run --region <test>` produces a valid `palms.geojson` that puts a point on at least 90% of the palms visible along inventory streets in the test neighbourhood.

## Context

- Exit criteria: `plans/05-phases.md` Phase 1; breakdown `plans/detailed/05-phases.md#phase-1-detection-mvp`.
- QA procedure and counts: SCAN-100 (`plans/detailed/02-detection-pipeline.md#w12-phase-1-deliverable-run`). If T1 ground truth (TEST-101) is already labelled, the `phase1_inventory` profile in `tests/accuracy/thresholds.yaml` can replace the eyeball count (`plans/detailed/06-testing.md#thresholds`).
- Test gating: TEST-001, TEST-004, TEST-100 (`plans/detailed/06-testing.md#which-tests-gate-which-phase`).
- The test region YAML is the ARCH-008 region that contains the DEC-004 block (see the Phase 1 section of the detailed plan).
- Sign-off: the user. No kill criterion at this gate.

## Steps

1. Check every `depends_on` task is `done`.
2. Fill in the Evidence list.
3. Open `qa_map.gpkg` over aerial imagery with the user (or read the `phase1_inventory` result) and confirm the count.
4. User decides pass or fail. Pass: `python3 scripts/tasks.py set GATE-P1 done --by user --note "<recall %>"`.

## Acceptance criteria

- [ ] At least 90% of palms visible on aerial imagery along at least three inventory streets in T1 have a `palms.geojson` point within 3 m (count of 50+ palms; SCAN-100 log), or `phase1_inventory` recall ≥ 0.90.
- [ ] `palms.geojson` passes the contract tests (`pytest tests/unit/contract -q`) and `python -m tests.helpers.contract <palms.geojson> --region regions/<test>.yaml` exits 0.
- [ ] `palmscan run --region <test> --offline` gives a byte-identical `palms.geojson` (SCAN-100).
- [ ] `qa_summary.md` shows `data_vintage` per source; any source older than about 5 years is flagged (R-04).
- [ ] The building footprint source is decided (ADR-0010) and `building_conflict` is set on the output.

## Evidence

- SCAN-100 run log: `tracking/logs/SCAN-100-run.md`
- QA summary path (in `data/`, not committed; paste the key lines into the log):
- Contract test run (CI link or pasted result line):
- T1 definition: `tests/sites/sites.yaml`
- Footprint decision: `tracking/decisions/ADR-0010-building-footprint-source.md`

## On fail

No kill criterion. Find why palms are missed, using the miss reasons in the SCAN-100 log:
- mis-normalised species names → extend `palmscan/data/species_aliases.csv` and rerun SCAN-100;
- palms missing from the inventory (private yards) → accept if the 90% target is met on inventory streets; otherwise note for Phase 4 (R-06);
- stale or wrong inventory → try another source in the region YAML, or revisit DEC-004 for a better-covered block.
Rerun SCAN-100 and this gate. If recall stays under 90% after two rounds, write the result here and ask the user whether to proceed with a lower target.

## Verification

```bash
python3 scripts/tasks.py show GATE-P1
grep -iE "recall|%|counted" tracking/logs/SCAN-100-run.md
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
