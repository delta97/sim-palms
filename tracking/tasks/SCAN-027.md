---
id: SCAN-027
title: "Decision tree species classifier with rules fallback"
status: done
phase: 4
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w18-species-classification"
depends_on: [SCAN-026]
requires: [none]
agent: lidar-analyst
estimate_h: 4
touches: [palmscan/classify/tree_model.py, tests/unit/palmscan/test_scan_tree_model.py]
owner: claude-agent
branch: task/scan-027-decision-tree-species-classifier-with-ru
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-027"
updated: 2026-11-22
---

## Goal

A small decision tree trained on inventory+LiDAR matches replaces the hand shape rules when it is measurably better, falls back to the rules otherwise, and is saved as plain JSON so inference is reproducible without scikit-learn.

## Context

- Spec: plan_ref section W18, `tree_model.py` part (steps 1-7) and source plan section 5 "Upgrade in Phase 4".
- Training input is `MergeResult.training` (list of `(PalmRecord, LidarCandidate)`), built by hand in tests.
- Compare against `shape_rules` from SCAN-026 on the same folds. Parameters from `ClassifyParams`.

## Steps

1. `TrainReport` dataclass; `TreeModel` with `predict`, `to_json`, `from_json`.
2. `train(training, params)`: label prep with `_other`, sample-size checks, `DecisionTreeClassifier(max_depth, min_samples_leaf, class_weight="balanced", random_state=0)`, 5-fold `StratifiedKFold(shuffle=True, random_state=0)` for tree and rules, gain check, final fit on all data, confusion matrix.
3. Numpy tree walk for `predict` from the exported arrays; confidence = leaf fraction x 0.9 clamped to [0.3, 0.85]; `_other` -> `None`.
4. Tests: separable synthetic data -> `used=True`; 30 samples -> `too_few_samples`; data where rules are already perfect -> `no_gain`; JSON round trip gives identical predictions; sklearn-free predict (monkeypatch `sys.modules["sklearn"] = None` after training).

## Acceptance criteria

- [x] Tree used only when CV accuracy beats rules by at least `tree_min_gain`.
- [x] JSON round trip reproduces predictions exactly.
- [x] Prediction works without scikit-learn importable.
- [x] `TrainReport` includes confusion matrix and reason.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_tree_model.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-027-decision-tree-species-classifier-with-ru worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-027
- 2026-11-22 [claude-agent] Plan W18 step 4 clarified: rules None counts right on _other samples (symmetric with tree), folds pooled out-of-fold; filifera labels fold into robusta; added save_model/load_model and rules kwarg. Task text unchanged otherwise.
- 2026-11-22 [claude-agent] Verified: test_scan_tree_model 16 passed; full suite 1651 passed 1 skipped; ruff, format, mypy clean. All acceptance boxes pass (gain gate, JSON round trip, sklearn-free predict, report with confusion+reason).
- 2026-11-22 [claude-agent] Status in_progress -> review.
- 2026-11-22 [integrator] Status review -> done.
