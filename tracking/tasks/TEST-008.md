---
id: TEST-008
title: Add optional image-diff scoring for visual viewpoints
status: todo
phase: 6
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#image-diff-scoring"
depends_on: [TEST-102]
requires: [none]
agent: test-engineer
estimate_h: 3
touches: [tests/visual/diff_score.py, tests/visual/diff_thresholds.yaml, tests/unit/visual/test_diff_score.py]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

`python -m tests.visual.diff_score <run_a> <run_b>` gives an SSIM and mean-absolute-difference score per viewpoint and flags changes, so visual regressions show up as numbers.

## Context

- Spec: `plans/detailed/06-testing.md#image-diff-scoring`.
- Scores flag things for a human; they never pass or fail a phase on their own.
- Thresholds are provisional until TEST-018 measures the noise floor.
- Uses scikit-image and Pillow (dev dependencies requested from ARCH-001).

## Steps

1. `tests/visual/diff_thresholds.yaml`: `ssim_min: 0.90`, `mad_max: 0.05`, `calibrated: false`, `noise_floor: null`.
2. `tests/visual/diff_score.py`: args `run_a run_b --variant static [--variant-b <v>] [--write] [--thresholds path]`. For each VP1-VP3: load both JPEGs, resize the larger to the smaller size (Lanczos), greyscale, optional mask `tests/visual/<site>/mask_<VP>.png` (white = compare; masked pixels excluded from MAD; for SSIM, use the full SSIM map from `structural_similarity(..., full=True, data_range=255)` and average it over the mask). MAD = mean |a − b| / 255.
3. Output: a table per viewpoint (ssim, mad, flagged). `--write` saves `<run_b>/diff/<VP>_heatmap.png` (absolute difference, scaled to 0-255) and `<run_b>/diff/scores.json`.
4. Exit 0 no flags, 1 any viewpoint flagged, 2 input error (missing images, different sites).
5. Tests with generated images: identical images give ssim 1.0 and mad 0 and exit 0; a 50 × 50 px block changed in a 400 × 300 image is flagged; a mask covering that block removes the flag; different image sizes are handled; missing VP2 gives exit 2.

## Acceptance criteria

- [ ] Scores and flags per viewpoint as specified; heatmaps written with `--write`.
- [ ] Mask support works.
- [ ] Tests pass.

## Verification

```bash
pytest tests/unit/visual/test_diff_score.py -q
python -m tests.visual.diff_score --help
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
