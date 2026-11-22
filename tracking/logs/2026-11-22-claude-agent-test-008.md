# Session log: 2026-11-22, claude-agent, test-008 image-diff scoring

- **Started / ended:** 2026-11-22 (local time, not recorded)
- **Agent / model / person:** claude-agent (Claude Haiku 5.5)
- **Branch / worktree:** task/test-008-add-optional-image-diff-scoring-for-visu, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-008
- **Tasks:** TEST-008 (in_progress -> review)

## Goal

Add optional image-diff scoring for the in-sim visual runs (TEST-102 tooling): per viewpoint SSIM
and mean absolute difference, flags against thresholds, heatmaps and scores.json with `--write`,
and mask support. Spec: `plans/detailed/06-testing.md#image-diff-scoring`.

## What changed

- `tests/visual/diff_score.py`: the CLI and scoring. `python -m tests.visual.diff_score RUN_A RUN_B
  [--variant V] [--variant-b V] [--write] [--thresholds PATH]`. Exit 0 no flags, 1 any flag, 2 input
  error. numpy, Pillow and scikit-image are imported only when a comparison runs, with one clear
  message if missing.
- `tests/visual/diff_thresholds.yaml`: `ssim_min: 0.90`, `mad_max: 0.05`, `calibrated: false`,
  `noise_floor: null`. Provisional until TEST-018. The comment records the TEST-018 formula.
- `tests/unit/visual/test_diff_score.py`: 15 tests with generated images in temp run folders.

## Verification

- `.venv/Scripts/python -m pytest tests/unit/visual/test_diff_score.py -q`: 15 passed.
- `.venv/Scripts/python -m tests.visual.diff_score --help`: exit 0, usage printed.
- `.venv/Scripts/python -m pytest -q`: 1791 passed, 3 skipped (network, PDAL binding, no local
  palmscan output).
- `ruff check .`: All checks passed. `ruff format --check .`: 158 files already formatted.
- `mypy`: Success, no issues in 73 source files.
- The venv needed the `gen`, `scan` and `lidar` extras too (palmscan and palmgen tests import
  geopandas, jinja2 and markupsafe). `pip install -e ".[dev]"` alone fails collection there. That
  is an environment gap, not caused by this task. Worth a note in the test README or ARCH-001.

## Decisions and findings

- **Spec discrepancy, not fixed in the spec text:** Step 5 says a 50 x 50 px block changed in a
  400 x 300 image is flagged. With the default thresholds (0.90 / 0.05) it is not: measured
  VP2 ssim 0.9815, mad 0.0101, no flag. The block test therefore uses explicit tight thresholds
  (`ssim_min 0.99`, `mad_max 0.005`) passed through `--thresholds`, so the flag comes from the code
  path under test. The masked case uses the same thresholds and must pass. TEST-018 should decide
  whether the default thresholds are too loose for small local changes.
- Resize: the larger image (by area) is resized to the smaller image's size with Lanczos. If the
  aspect ratios differ, the result is stretched; real runs share the same capture size.
- Masks: `tests/visual/<site>/mask_<VP>.png`, looked up in the folder that holds RUN_A. Greyscale
  value >= 128 means compare. The mask is resized to the compared size with nearest neighbour.
  SSIM is the mean of the full SSIM map over masked-in pixels. MAD is over the same pixels.
  A mask that excludes every pixel is an input error (exit 2).
- Heatmap: |a - b| in greyscale is already 0 to 255, so it is written as is (no stretch), with
  masked-out pixels set to 0. Stretching to the maximum would make noise look like change.
- `scores.json` stores run folders as `<date>[_<label>]` labels, not absolute paths, so it can be
  committed. The file is written to `<run_b>/diff/`. Whether `diff/` is committed is left to the
  visual-run process; `raw/` stays gitignored.
- `--variant` defaults to `static`. `--variant-b` defaults to the same name as `--variant`.
- Scores flag only. Nothing here passes or fails a phase.

## Open issues

- Default thresholds may be too loose for small local changes (see above). Settle in TEST-018.
- Thresholds are provisional (`calibrated: false`). No noise floor measured yet.

## Handoff: next steps

1. TEST-018 (on the sim PC): capture two no-fix runs at T1 in one session, run
   `python -m tests.visual.diff_score <run_a> <run_b> --variant nofix --write`, then set
   `ssim_min` and `mad_max` in `tests/visual/diff_thresholds.yaml` using the formulas in its comment,
   fill `noise_floor`, and set `calibrated: true`.
2. Reviewer: check the default-threshold finding above before TEST-018 starts.
