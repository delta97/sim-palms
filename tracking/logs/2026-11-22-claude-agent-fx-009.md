# Session log: 2026-11-22, claude-agent, fx-009 calibration

- **Started / ended:** 2026-11-22
- **Agent / model / person:** claude-agent
- **Branch / worktree:** task/fx-009-calibration-clicks-tool-vfov-time-offset, sim-palms-worktrees/FX-009
- **Tasks:** FX-009 (in_progress -> review)

## Goal

Clicks storage/UI, calibration solver (vfov, time offset, pose bias, depth model), `palmfx calib` and `palmfx clicks`.

## What changed

- `palmfx/offline/calib.py`: `calibrate`, `CalibResult`, `write_calib`, `write_metric_depth`, `warnings_for`.
- `palmfx/offline/clicks.py`: `clicks.json` format, `ClickBook` (save per click, undo, resume), `parse_label`, overlay, lazy-matplotlib `run_click_ui`.
- `palmfx/offline/commands/{calib,clicks}.py`: the two subcommands.
- `tests/unit/palmfx/test_calib.py`: synthetic recovery and command tests.
- `plans/detailed/08-image-layer-experiment.md`: identifiability note in A6.

## Verification

`python scripts/ci.py`: ruff, format, mypy, pytest (2023 passed, 3 skipped), tasks validate/conflicts all PASS.

## Decisions and findings

- Straight constant-velocity flight cannot separate time offset from forward `d_body_m` (first attempt returned 106 ms for a true 40). The test flight therefore changes attitude (poses.csv rewritten in the test), and the solver adds a weak `d_body_m` prior (3 px/m). Heading bias also trades against lateral body offset.
- Depth pairs get gross-outlier trimming (worst pair removed while > 10 % off), needed for bases hidden behind the building.
- `a` and `b` of the depth model are collinear over a narrow range; judge the model by `rms_rel`. The test blob is 0.5 m wide so the depth sampled at a base is not biased by the front face.
- The 8 px target scales with height, so a 180 p synthetic fit with 1 px noise is flagged (tested).

## Open issues

- `run_click_ui` is untested on a display (manual check in the task). Real captures (FX-013) must include attitude change or a known camera offset.

## Handoff: next steps

1. User: run the manual click check on a desktop, then FX-013 clicks on real frames.
