# Tracking

How work on sim-palms is recorded. The protocol is in [`AGENTS.md`](../AGENTS.md); this page explains the files.

## Summary

- **Tasks** are files: `tasks/<ID>.md`. Frontmatter holds status and metadata; the body holds the spec and an append-only Log.
- **The board** (`BOARD.md`) is generated from the task files. Never edit it by hand.
- **Session logs** (`logs/`) are one file per work session and end with a handoff.
- **Decisions** (`decisions/`) are ADRs; agents propose, the user accepts.
- **STATUS.md** is the short human summary of where the project stands.

## Task ids

| Prefix | Area | Detailed plan |
|---|---|---|
| `ARCH` | Python foundation: palmcore, schemas, config, CLI, CI | `plans/detailed/01-architecture.md` |
| `SCAN` | palmscan detection pipeline | `plans/detailed/02-detection-pipeline.md` |
| `ASSET` | Palm model library | `plans/detailed/03-palm-assets.md` |
| `GEN` | palmgen scenery generator | `plans/detailed/04-fs2024-integration.md` |
| `LIVE` | palmlive companion app | `plans/detailed/04-fs2024-integration.md` |
| `SPIKE` | Phase 0 feasibility spikes | `plans/detailed/05-phases.md` |
| `REGION` | Phase 6 per-region scale-out | `plans/detailed/05-phases.md` |
| `GATE` | Phase exit gates `GATE-P0`..`GATE-P7` | `plans/detailed/05-phases.md` |
| `TEST` | Cross-cutting test layers | `plans/detailed/06-testing.md` |
| `DEC` | Decisions the user makes | `plans/detailed/07-risks-and-open-questions.md` |
| `RISK` | Cross-cutting risk work (licenses, mod masks, update watch) | `plans/detailed/07-risks-and-open-questions.md` |
| `FX` | Image-layer experiment | `plans/detailed/08-image-layer-experiment.md` |
| `INFRA` | Repo and tracking infrastructure | this file |

Numbers `001`-`099` are ordinary tasks. `100`-`199` are deliverables or interfaces other areas depend on
(for example `GEN-100`: "palmgen build produces a working Community package").

## Key frontmatter fields

| Field | Why it matters |
|---|---|
| `status` | `todo`, `in_progress`, `blocked`, `review`, `done`, `dropped`. "Ready" is computed. |
| `depends_on` | Drives readiness. Keep it minimal and real. |
| `requires` | Which environment can do the task: `none`, `network`, `windows-sim`, `blender`, `gpu`, `human`. |
| `touches` | Paths the task changes. `tasks.py batch` uses it to avoid parallel conflicts. |
| `agent` | Suggested specialist in `.claude/agents/`. |
| `owner`, `branch`, `worktree` | Who has it and where the work is happening. |

Full field reference: [`tasks/_TEMPLATE.md`](tasks/_TEMPLATE.md).

## GitHub issues

Each task is mirrored to a GitHub issue (`issue:` field). Gate issues are the parents of their phase's tasks.
Issues are a read-mostly progress view generated from these files by `scripts/issues.py sync`, which the integrator runs locally after every push to `main`.
Details: `AGENTS.md` section 5a.

## Commands

```bash
python3 scripts/tasks.py validate                    # run before and after editing tasks; CI runs it too
python3 scripts/tasks.py ready --requires none       # what a Linux/cloud agent can start now
python3 scripts/tasks.py batch --requires none --max 4   # a parallel-safe set
python3 scripts/tasks.py list --phase 0              # everything in a phase
python3 scripts/tasks.py list --needs windows-sim,blender,gpu,human --status todo   # what is waiting on the user
python3 scripts/tasks.py conflicts                   # same-path tasks with no dependency ordering
python3 scripts/tasks.py board                       # regenerate BOARD.md (on main)
```

## Recap

- One file per task, one file per session, one file per decision: parallel branches rarely collide.
- Shared summaries (`STATUS.md`, `BOARD.md`, `CHANGELOG.md`) change only on `main`.
- `requires` and `touches` are what make parallel and mixed-environment work safe. Keep them accurate.
