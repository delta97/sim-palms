# sim-palms

Replacing palm tree block artifacts in photogrammetry in Microsoft Flight Simulator 2024 with actual palm tree artifacts.

**Status:** the offline Python tooling is built and tested on fixtures (palm detection from inventories and LiDAR, scenery-generator building blocks, test and image-layer tooling). Nothing has run in the sim yet: the sim-PC spikes come next. Current state: [`tracking/STATUS.md`](tracking/STATUS.md).

## How it works

1. **Find the real palms** from city tree inventories and USGS LiDAR (`palmscan` → `palms.geojson`).
2. **Cut the photogrammetry blob** at each palm with `ExcludeTIN` polygons, generated as a Community package (`palmgen` + `fspackagetool`).
3. **Place a 3D palm** of the right species and height (`assets/` model library; static placement or live SimConnect spawning, decided by measurement).
4. **Switch regions on and off** with a small companion app (`palmlive`).

## Where to look

| You want to | Read |
|---|---|
| Understand the plan | [`plans/README.md`](plans/README.md), then `plans/01`-`08` |
| See executable detail per area | [`plans/detailed/`](plans/detailed/README.md) |
| See what's ready, in progress, blocked | [`tracking/BOARD.md`](tracking/BOARD.md) (generated) |
| Pick up work (any agent or person) | [`AGENTS.md`](AGENTS.md): start-of-session checklist, task lifecycle, worktrees, logging |
| See past sessions and handoffs | [`tracking/logs/`](tracking/logs/) |
| See decisions | [`tracking/decisions/`](tracking/decisions/README.md) |

## Quick start

```bash
python scripts/ci.py --install      # once: .venv with dev,scan,lidar,gen,fx extras
python scripts/ci.py                # local CI: lint, types, tests + coverage, tracking checks
.venv/Scripts/palmscan run --region san-diego-coastal   # find palms (live sources; not yet run on a full region) -> build/scan/<region>/palms.geojson
.venv/Scripts/palmfix validate build/scan/san-diego-coastal/palms.geojson
```

GitHub Actions is disabled for this repo; `scripts/ci.py` is the CI. Test layers and commands: [`tests/README.md`](tests/README.md).

## Quick start for an agent

```bash
python3 scripts/tasks.py validate
python3 scripts/tasks.py ready --requires none
python3 scripts/tasks.py show <TASK-ID>
```

Then follow `AGENTS.md` section 3. In Claude Code: `/start-task <ID>`, `/plan-batch`, `/handoff`.
