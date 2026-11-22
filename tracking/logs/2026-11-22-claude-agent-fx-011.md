# Session log: 2026-11-22, claude-agent, fx-011 heuristic masks

- **Started / ended:** 2026-11-22
- **Agent / model / person:** claude-agent
- **Branch / worktree:** task/fx-011-mask-by-depth-and-colour-heuristics, sim-palms-worktrees/FX-011
- **Tasks:** FX-011 (in_progress -> review)

## Goal

Blob masks from raw depth and colour alone (plan 08, A8), output as session masks for FX-012.

## What changed

- `palmfx/offline/mask_heuristic.py`: `HeuristicParams.from_yaml`, `heuristic_masks`, `debug_overlay`.
- `palmfx/offline/config/heuristic.yaml`: every threshold, plus the added `regrow_depth_tol`.
- `palmfx/offline/commands/mask_heuristic.py`: `palmfx mask-heuristic`.
- `tests/unit/palmfx/test_mask_heuristic.py`: 14 tests on the synthetic scene.
- `plans/detailed/08-image-layer-experiment.md`: A8 implementation notes.

## Verification

`python scripts/ci.py`: ruff, format, mypy, pytest (2023 passed, 3 skipped), tasks validate and conflicts all PASS.
`mask-compare --a heuristic --b gt` on the synthetic session: pixel IoU mean 0.827, precision 1.00, recall 0.80.

## Decisions and findings

- Without regrow the synthetic IoU is 0.59: the lower third of a blob is within 10 % of the ground depth beside it. Regrow (an addition to the plan) gives 0.83.
- Grass has the same hue as the blob in the synthetic scene, so colour alone cannot reject lawn; the depth protrusion does.
- The farthest synthetic blob (about 190 m) is missed (aspect fails); blobs wider than the opening are missed by design.
- `reversed` is read from `session.json` (default true). Sobel scale and edge tolerance were unspecified in the plan. All VERIFY, tune in FX-019.

## Open issues

No real-capture validation. Sky value and depth polarity of MSFS 2024 are unconfirmed (FX-001).

## Handoff: next steps

1. FX-012/FX-019: run `palmfx mask-heuristic` on real sessions, compare against `hand` and `project-depth`, tune `config/heuristic.yaml`.
