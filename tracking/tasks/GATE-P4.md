---
id: GATE-P4
title: "Phase 4 exit gate: LiDAR accuracy targets met and beach site fixed in the sim"
status: todo
phase: 4
area: GATE
kind: gate
plan_ref: "plans/detailed/05-phases.md#phase-4-lidar-enrichment"
depends_on: [GATE-P2, SCAN-101, TEST-012, DEC-006]
requires: [human, windows-sim]
agent: task-planner
estimate_h: 2
touches: [tests/visual/T2/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

The user confirms that LiDAR gives real heights and finds the palms the inventories miss: accuracy targets met against hand labels, and the beach site (T2, no inventory) visibly fixed in the sim.

## Context

- Exit criteria: `plans/05-phases.md` Phase 4; breakdown `plans/detailed/05-phases.md#phase-4-lidar-enrichment`.
- Thresholds: `tests/accuracy/thresholds.yaml` (`plans/detailed/06-testing.md#thresholds`): profile `lidar_only` precision ≥ 0.90, recall ≥ 0.80; `height_error_median_max_m: 2.0`.
- Test gating: TEST-012 evaluation; in-sim visual at T2 with C1, C2 (`plans/detailed/06-testing.md#which-tests-gate-which-phase`).
- The beach-site in-sim check belongs to this gate (`plans/detailed/02-detection-pipeline.md#w21-threshold-tuning-and-phase-4-deliverable`), which is why it needs the sim PC.
- This gate depends on GATE-P2, not GATE-P3: Phase 4 can run in parallel with Phase 3 (different machines and people). Use `--models library` if ASSET-100 is done, else `--models placeholder`.
- Kill criterion K6 (`plans/detailed/07-risks-and-open-questions.md#kill-criteria`).
- Sign-off: the user.

## Steps

1. Check every `depends_on` task is `done`.
2. On the sim PC: `palmgen build --region <region containing T2> --models <library|placeholder>` with the SCAN-101 `palms.geojson`; activate the package.
3. Visual protocol at T2: `python -m tests.visual.new_run --site T2 --label phase4 --sim-version <v> --region-pkg <ver> --variants nofix,static`, take VP1-VP3 for both variants, `finalize`, fill the checklist, `python -m tests.visual.check_run <run_dir> --update-log`.
4. Fill in the Evidence list.
5. User decides pass or fail. Pass: `python3 scripts/tasks.py set GATE-P4 done --by user`.

## Acceptance criteria

- [ ] `lidar_only` at T1 and T2: precision ≥ 0.90 and recall ≥ 0.80 (TEST-012 results, `metrics evaluate` exit 0).
- [ ] T4 (false-positive site): precision ≥ 0.90 (cypress, eucalyptus and poles not counted as palms).
- [ ] Median height error on matched palms < 2.0 m (TEST-012 / SCAN-101 report).
- [ ] T2 beach visual run: C1 (blobs gone) and C2 (a palm at every former blob, believable height) pass at VP1-VP3; `check_run` result `pass`.
- [ ] ADR-0007 (scope beyond palms) is accepted, so the classifier classes are fixed.

## Evidence

- Accuracy results: `tests/accuracy/T1/results/`, `tests/accuracy/T2/results/`, `tests/accuracy/T4/results/`
- SCAN-101 log: `tracking/logs/SCAN-101-run.md`
- Tuning log: `tracking/logs/SCAN-030-tuning.md`
- T2 run folder: `tests/visual/T2/<date>_phase4/`
- Scope decision: `tracking/decisions/ADR-0007-scope-beyond-palms.md`

## On fail

- **LiDAR-only precision stays under 0.80 after tuning (K6):** drop LiDAR-only palms; keep LiDAR heights for inventory palms only. Phase 4 ends without the beach site. Record it and pass the gate with reduced scope if the user agrees.
- **Precision 0.80-0.90 or recall under 0.80:** one more SCAN-030 tuning round, then re-evaluate. If still short, the user decides whether to accept with lower targets (write the numbers here).
- **Height error ≥ 2 m:** check CHM resolution and the inventory-LiDAR match radius (SCAN-025); rerun.
- **T2 visual fails:** palms found but cut or placement wrong → GEN fix; palms not found → back to SCAN-030.

## Verification

```bash
ls tests/accuracy/T1/results/ tests/accuracy/T2/results/ tests/accuracy/T4/results/
grep "T2" tests/visual/test_log.md
python3 scripts/tasks.py show GATE-P4
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
