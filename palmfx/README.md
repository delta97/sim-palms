# palmfx

Image-layer experiment for sim-palms (plan 08, area FX). Optional; it has a kill switch.

**Stage A** is offline: record colour, depth and camera pose from the sim, build palm-blob masks
(projection and depth/colour), erase them with an inpainting model, stabilise over time, draw a
palm sprite, and judge. Stage B (a ReShade add-on) only starts if Stage A passes its go/no-go.

- Code: `palmfx/offline/` (session I/O in `session.py`, one CLI subcommand per file in
  `palmfx/offline/commands/`).
- Data: `data/fx/<session_id>/` (gitignored, large). Layout is in the plan.
- Install: `pip install -e .[fx]`
- Run: `palmfx --help` or `python -m palmfx.offline --help`. Every command takes
  `--session data/fx/<session_id>`.
- Add a command: drop a module with `register(subparsers)` into `palmfx/offline/commands/`.
- Plan: `plans/detailed/08-image-layer-experiment.md#scope-and-interfaces`
