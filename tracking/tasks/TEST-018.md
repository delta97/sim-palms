---
id: TEST-018
title: Calibrate the image-diff noise floor at T1
status: todo
phase: 6
area: TEST
kind: test
plan_ref: "plans/detailed/06-testing.md#image-diff-scoring"
depends_on: [TEST-008, TEST-104]
requires: [windows-sim]
agent: test-engineer
estimate_h: 2
touches: [tests/visual/diff_thresholds.yaml, tests/visual/T1/<date>_calib-a/, tests/visual/T1/<date>_calib-b/, tests/visual/T1/<date>_calib-c/, tests/visual/T1/mask_<VP>.png, tests/visual/test_log.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

`tests/visual/diff_thresholds.yaml` holds thresholds based on measured noise (two identical-setup runs), so image-diff flags mean a real change rather than streaming or lighting noise.

## Context

- Spec: `plans/detailed/06-testing.md#image-diff-scoring` (calibration rule). Tools: TEST-102 (runs), TEST-008 (scores).
- Photogrammetry streaming and lighting can differ between two identical runs; that difference is the noise floor.

## Steps

1. Two no-fix runs at T1 in one session, same flight, same viewpoints: `new_run --site T1 --label calib-a --variants nofix`, then `calib-b`. Restart the flight between them (not the sim).
2. A third run after a full sim restart: `calib-c`.
3. Score `calib-a` vs `calib-b` and `calib-a` vs `calib-c` with `python -m tests.visual.diff_score ... --variant nofix --write`.
4. Take the lowest SSIM and highest MAD across all viewpoints and both pairs as the noise floor. Set `ssim_min = noise_ssim_min − 0.03`, `mad_max = noise_mad_max + 0.02`, `calibrated: true`, `noise_floor: {ssim_min: ..., mad_max: ..., date: ..., sim_version: ...}`.
5. If the noise floor is so high that real changes can't be seen (SSIM below 0.8), note in the Log that diff scoring isn't useful at that viewpoint and add a mask (`tests/visual/T1/mask_<VP>.png`) over the noisy areas (sky, distant terrain), then rescore.

## Acceptance criteria

- [ ] Three calibration runs committed and in `test_log.md`.
- [ ] `diff_thresholds.yaml` updated with `calibrated: true` and the measured noise floor.

## Verification

```bash
grep -n "calibrated: true" tests/visual/diff_thresholds.yaml
python -m tests.visual.diff_score tests/visual/T1/<date>_calib-a tests/visual/T1/<date>_calib-b --variant nofix; echo "exit=$?"   # 0: no flags between noise-only runs
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Narrowed touches from tests/visual/T1/ to the three labelled calibration runs and the mask files, so it no longer overlaps GEN-019. Cross-area reconciliation.
- 2026-11-22 [integrator] integrator note from TEST-008: with default thresholds (ssim 0.90 / mad 0.05) a 50x50 block change in a 400x300 frame is NOT flagged (ssim 0.9815, mad 0.0101); calibrate defaults here
