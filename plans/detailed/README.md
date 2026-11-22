# Detailed plans

Executable breakdowns of the original plan files in `plans/`. Each one specifies interfaces, work breakdown,
a task index, a dependency graph, parallelization notes, verification and open questions. Tasks live in
`tracking/tasks/` and point back here through their `plan_ref`.

Written 2026-11-21/22, one subagent per plan file, then reconciled across areas (each file has a
"Reconciliation notes" section listing what changed).

| File | Source | Task areas | Tasks |
|---|---|---|---|
| [01-architecture.md](01-architecture.md) | `plans/01-architecture.md` | ARCH | 9 |
| [02-detection-pipeline.md](02-detection-pipeline.md) | `plans/02-detection-pipeline.md` | SCAN | 26 |
| [03-palm-assets.md](03-palm-assets.md) | `plans/03-palm-assets.md` | ASSET | 41 |
| [04-fs2024-integration.md](04-fs2024-integration.md) | `plans/04-fs2024-integration.md` | GEN, LIVE | 20 + 14 |
| [05-phases.md](05-phases.md) | `plans/05-phases.md` | SPIKE, GATE, REGION | 11 + 8 + 14 |
| [06-testing.md](06-testing.md) | `plans/06-testing.md` | TEST | 23 |
| [07-risks-and-open-questions.md](07-risks-and-open-questions.md) | `plans/07-risks-and-open-questions.md` | DEC, RISK | 11 + 9 |
| [08-image-layer-experiment.md](08-image-layer-experiment.md) | `plans/08-image-layer-experiment.md` | FX | 26 |

Start with `05-phases.md`: it maps every task to its phase, shows the critical path, the revised effort and what can run in parallel.

## Revised effort (sum of task estimates, hours)

| Phase | Original | Detailed | Of which needs sim PC, Blender, GPU or the user |
|---|---|---|---|
| 0 Feasibility spike | 6–10 | 33 | 18.5 |
| 1 Detection MVP | 8–15 | 93.5 | 13.5 |
| 2 Generator MVP | 8–12 | 70.5 | 13.5 |
| 3 Palm asset library | 20–40 | 131 | 105.5 |
| 4 LiDAR enrichment | 10–20 | 55 | 17 |
| 5 Bake-off and companion app | 10–25 | 74.5 | 34.5 |
| 6 Scale-out | 5–10 per region | 119.5 | 106.5 |
| 7 Image-layer experiment | 10–20 | 103.5 | 53.5 |
| **Total** | ~80–150 | **680.5** | **362.5** |

The growth is mostly tests and tooling, the shared `palmcore` foundation, Florida models, placeholder regions and FX Stage B.
Roughly half the hours are Linux-container code work that agents can do; the user's sim and Blender time is the real constraint.
