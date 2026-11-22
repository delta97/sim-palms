# Session log: 2026-11-22, claude-agent, fx-010

- **Started / ended:** 2026-11-22
- **Agent / model / person:** claude-agent
- **Branch / worktree:** task/fx-010-mask-by-projection-from-palms-geojson, sim-palms-worktrees/FX-010
- **Tasks:** FX-010 (in_progress -> review)

## Goal

Blob masks by projecting palms.geojson into each frame, raw and depth-tested (plan 08 A7).

## What changed

- `palmfx/offline/mask_project.py`: ProjectParams, palm loading and defaults, ground-elevation fill, billboard, project_masks.
- `palmfx/offline/commands/mask_project.py`: `palmfx mask-project`.
- `tests/unit/palmfx/test_mask_project.py`: 16 tests on the synthetic scene.
- `plans/detailed/08-image-layer-experiment.md`: A7 implementation notes.

## Verification

- `pytest tests/unit/palmfx/test_mask_project.py`: 16 passed.
- `python scripts/ci.py`: all PASS (2025 passed, 3 skipped).

## Decisions and findings

- Quad rasterised by pixel-centre sampling; cv2.fillPoly overpaints outline pixels.
- Plan default dilate_px=3 is too much for tiny synthetic blobs; tests use dilate 0, width_scale 1.2.
- palms.geojson schema requires height_m and crown_diam_m, so defaults only apply with `--lenient-palms`.
- project_masks takes (palms, K, pose, depth_m, params, occluder) and returns a ProjectResult; the task text's `frame` argument was dropped (not needed).

## Open issues

- VERIFY: `calib/camera.json` name/keys (FX-009); `alt_agl_m` pose key (FX-006).

## Handoff: next steps

1. FX-019 runs `palmfx mask-project` on real sessions once FX-009 writes depth.npy and calibration.
