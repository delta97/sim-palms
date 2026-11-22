# AGENTS.md: Operating protocol for any agent or person working on sim-palms

This file is the single source of truth for **how** work happens in this repo. It applies to
every model and every person. `CLAUDE.md` imports it; other tools should be pointed at it.

**The project:** remove the green "blob" palms that MSFS 2024 photogrammetry renders, and put real
3D palms in their place, generated from public tree and LiDAR data. Plans are in `plans/`.

---

## 1. Map of the repo

| Path | What it is | Who edits it |
|---|---|---|
| `plans/*.md` | Original plan set (2026-11-21). Read-only reference. | Nobody, except to fix a confirmed error (log it) |
| `plans/detailed/*.md` | Executable breakdown of each plan file | Task owners when the spec changes |
| `tracking/STATUS.md` | Human-readable "where are we" summary | Integrator, at the end of a session on `main` |
| `tracking/BOARD.md` | Generated task board. **Never edit by hand.** | `python3 scripts/tasks.py board` |
| `tracking/tasks/<ID>.md` | One file per task: spec, status, owner, log | The task's owner |
| `tracking/logs/*.md` | One file per work session: what changed and the handoff | The session that wrote it |
| `tracking/decisions/ADR-*.md` | Accepted and proposed decisions | Proposed by agents, accepted by the user |
| `CHANGELOG.md` | One line per merged task | Integrator, at merge |
| `scripts/tasks.py` | Task CLI: list, ready, batch, claim, set, log, validate, board | |
| `scripts/wt.sh` | Worktree helper for parallel work | |
| `scripts/ci.py` | Local CI (GitHub Actions is disabled): lint, types, tests + coverage, tracking checks. Must pass before merging to `main` | |
| `scripts/issues.py` | Mirrors task files to GitHub issues (titles, bodies, labels, open/closed, gate sub-issues). Run locally by the integrator after pushing `main`: `python scripts/issues.py sync` | |
| `.claude/agents/*.md` | Specialist subagents for this project | |
| `.claude/skills/*/SKILL.md` | Repeatable procedures: `/start-task`, `/handoff`, `/plan-batch` | |

---

## 2. Start of every session (5 minutes, do not skip)

1. Read `tracking/STATUS.md` (current phase, blockers, what's next).
2. Read the newest file in `tracking/logs/` (the last handoff).
3. Run:
   ```bash
   python3 scripts/tasks.py validate
   python3 scripts/tasks.py ready --requires none
   ```
   `--requires none` lists tasks a cloud/Linux agent can do with no sim, Blender, GPU or human.
   Use `--requires none,network` if you have internet access to data sources.
4. If the user named a task, use it. Otherwise pick the lowest-phase ready task.
5. Read the task file and its `plan_ref` section before touching code.

---

## 3. Task lifecycle

```
todo ──claim──> in_progress ──open PR / ask review──> review ──merge──> done
  │                  │
  │                  └──> blocked (say why in the Log; create the unblocking task)
  └──> dropped (say why)
```

"Ready" is computed, not stored: a `todo` task whose `depends_on` are all `done`.

| Step | Command |
|---|---|
| See what's ready | `python3 scripts/tasks.py ready --requires none` |
| Read a task | `python3 scripts/tasks.py show SCAN-003` |
| Claim (single checkout) | `python3 scripts/tasks.py claim SCAN-003 --owner <you> --branch <branch>` |
| Claim + worktree (parallel) | `scripts/wt.sh new SCAN-003 --owner <you> [--push]` |
| Log progress | `python3 scripts/tasks.py log SCAN-003 "Adapter parses fixture; 12 tests pass" --by <you>` |
| Block | `python3 scripts/tasks.py set SCAN-003 blocked --by <you> --note "needs fixture from SCAN-002"` |
| Ready for review | `python3 scripts/tasks.py set SCAN-003 review --by <you>` |
| Done (after merge) | `python3 scripts/tasks.py set SCAN-003 done --by <integrator>` |
| New task found mid-work | `python3 scripts/tasks.py new SCAN --title "..." --phase 1`, then fill it in |

**Rules:**
- One task per branch. If a task grows past ~6 hours, split it and record the split in both Logs.
- Do the task's Verification steps before setting `review`. Paste the result line into the Log.
- Tick the Acceptance criteria checkboxes in the task file as they pass.
- Never mark `done` your own unreviewed work. `review` is the end state for the implementer.
- If the spec in `plan_ref` is wrong, fix the detailed plan in the same branch and say so in the Log.

---

## 4. Parallel work with worktrees

Use worktrees when two or more tasks run at the same time on one machine (several agents, or you
plus agents). Each task gets its own branch and directory, so builds and tests don't collide.

**Choosing a parallel batch:**
```bash
python3 scripts/tasks.py batch --requires none --max 4
```
`batch` returns ready tasks whose `touches` paths don't overlap with each other or with anything
already `in_progress`. That overlap check is the main conflict-avoidance mechanism, so keep
`touches` accurate when you create or edit tasks. After adding or editing tasks, run
`python3 scripts/tasks.py conflicts`: it lists open tasks that touch the same path with no
dependency ordering between them. Fix each one with a real `depends_on` edge or narrower `touches`.

**Starting one:**
```bash
scripts/wt.sh new SCAN-003 --owner agent-scan-1 --push
cd "$(scripts/wt.sh path SCAN-003)"
```
`wt.sh new` claims the task on the current branch (normally `main`), commits the claim, and
creates `task/scan-003-<slug>` in `../sim-palms-worktrees/SCAN-003`. With `--push`, the push of the
claim commit acts as a lock: if another session claimed first, the push is rejected and the claim
is rolled back. Use `--push` whenever more than one machine or cloud session is working.

**What a task branch may touch:**
- Its own task file, the paths in its `touches`, its own session log, and the detailed plan
  section it implements.
- **Not** `tracking/STATUS.md`, `tracking/BOARD.md` or `CHANGELOG.md`. Those are shared and are
  updated only on `main` by whoever merges. This is what keeps parallel branches merge-clean.

**Merging (integrator):**
1. Review against the task's Acceptance criteria (the `code-reviewer` agent can do the first pass).
2. Merge the branch into `main` (squash or merge commit; keep the `Task:` trailer).
3. `python3 scripts/tasks.py set <ID> done --by <you>`; add one line to `CHANGELOG.md`.
4. `python3 scripts/tasks.py board`; update `tracking/STATUS.md` if the phase picture changed.
5. `scripts/wt.sh remove <ID> --delete-branch`.
6. Rebase or merge `main` into the other open task branches if they depend on what just landed.

**Cloud sessions** are often pinned to an assigned branch (for example `claude/<name>`). In that
case skip `wt.sh`, claim with `tasks.py claim --branch <assigned-branch>`, and follow the same
touch rules. One cloud session = one task (or one tightly related set) = one PR.

---

## 5. Logging: what goes where

| Record | When | Content |
|---|---|---|
| Task `## Log` | Every meaningful step | Dated one-liners: claimed, finding, verification result, commit sha, status change |
| Session log `tracking/logs/YYYY-MM-DD-<who>-<slug>.md` | One per session, written before you stop | Goal, files changed, verification, findings, open issues, **handoff next steps**. Template: `tracking/logs/_TEMPLATE.md` |
| ADR `tracking/decisions/ADR-NNNN-<slug>.md` | When a choice affects more than one task | Context, options, decision, consequences. Agents write `proposed`; only the user moves it to `accepted` |
| `CHANGELOG.md` | At merge | One line: `- TASK-ID: what changed (PR link)` |
| `tracking/STATUS.md` | End of session on `main` | Current phase, what's moving, what's blocked on the user, link to the newest log |

A new session must be able to continue from the task file, the newest session log and STATUS.md
alone, without chat history. Write for that reader.

### 5a. GitHub issues (progress view)

Every task has a GitHub issue titled `[<ID>] <title>`. Its number is in the task's `issue:` field.
Each phase's gate issue (`[GATE-Pn]`) is the parent of that phase's tasks, so the gate shows the phase's progress.

- **The task file is canonical.** The integrator runs `python scripts/issues.py sync` locally after every push to
  `main` (GitHub Actions is disabled for this repo): it creates issues for new tasks, regenerates bodies, and sets
  `status:*` labels and open/closed state from the file.
  Edit the task file, never the issue body. Comments on issues are fine and are not overwritten.
- **Commits and PRs:** reference the issue with `Refs #N`. Do **not** write `Closes #N`: the issue closes when the
  integrator sets the task to `done` on `main`; closing it earlier would be reverted by the next sync.
- **Filters that are useful:** `label:needs-user` (waiting on the sim PC, Blender, a GPU or the user),
  `label:status:in_progress`, `label:phase:1`, `label:area:scan`.
- `python scripts/issues.py sync --dry-run` shows what would change; it needs the `gh` CLI, logged in.

---

## 6. Branches and commits

- Integration branch: `main`. Task branches: `task/<id-lowercase>-<slug>` (made by `wt.sh`).
- Commit subject: `<area>(<TASK-ID>): <imperative summary>`, for example
  `scan(SCAN-003): add ArcGIS REST inventory adapter`. Tracking-only commits: `chore(tracking): ...`.
- Add a trailer line `Task: SCAN-003` to every commit for a task.
- Small commits. Never commit `data/`, `build/`, credentials, or large binaries outside the agreed
  asset storage (see the asset-storage decision once it exists).

---

## 7. Environments: who can do what

Every task declares `requires`. Respect it.

| `requires` | Who can do it | What to do if you can't |
|---|---|---|
| `none` | Any agent in any Linux container | |
| `network` | Agents with internet access to the data source | Record fixtures where you can; otherwise leave it |
| `windows-sim` | Only on the user's Windows PC with MSFS 2024 + SDK | Prepare a step-by-step runbook in the task, set the task to `blocked` with note "awaiting user on sim PC" |
| `blender` | A machine with Blender + the MSFS 2024 exporter | Same as above |
| `gpu` | A machine with a local GPU | Same as above |
| `human` | The user (judgement, purchase, labelling, decision) | Prepare the options and evidence, then ask |

Never fake a `windows-sim` or `human` result. If a result is missing, the task stays open.

---

## 8. Specialist agents (`.claude/agents/`)

| Agent | Use it for |
|---|---|
| `task-planner` | Picking ready work, proposing parallel batches, splitting oversized tasks, keeping dependencies honest |
| `python-architect` | `palmcore/`, schemas, packaging, CLI wiring, CI (area ARCH) |
| `geo-data-engineer` | `palmscan` source adapters, normalization, merge, QA outputs (area SCAN, inventory side) |
| `lidar-analyst` | PDAL pipelines, CHM, peak and crown detection, species classifier (area SCAN, LiDAR side) |
| `scenery-generator-engineer` | `palmgen`: geometry, XML from templates, tiling, GUIDs, package project (area GEN) |
| `msfs-sdk-specialist` | SDK, Dev Mode, `fspackagetool`, package definitions, sim-PC runbooks (SPIKE, GEN in-sim) |
| `asset-pipeline-artist` | Blender models, LODs, materials, glTF export, asset manifest and checks (area ASSET) |
| `simconnect-dotnet-engineer` | `palmlive` C#: region manager, spawn manager, SimConnect adapter (area LIVE) |
| `test-engineer` | Shared test harness, golden files, accuracy metrics, visual and perf protocols (area TEST) |
| `render-fx-researcher` | `palmfx` image-layer experiment (area FX) |
| `code-reviewer` | Reviewing a task branch against its acceptance criteria and these rules |
| `scribe` | Session logs, STATUS.md, CHANGELOG, board regeneration, handoffs |

Each task's `agent` field names the suggested specialist.

---

## 9. Definition of done (for a task)

- [ ] Every Acceptance criterion is ticked, with evidence in the Log.
- [ ] Verification commands pass; unit tests added for new code; `python3 scripts/tasks.py validate` passes.
- [ ] `python scripts/ci.py` passes on the branch (it replaces GitHub CI, which is disabled).
- [ ] Only files in `touches` (plus the task file, session log and plan section) changed. If more, update `touches` and say why.
- [ ] Docs or detailed plan updated if behaviour or interfaces changed.
- [ ] Reviewed by someone other than the implementer, then merged.

---

## 10. Ground rules

- **Don't invent MSFS SDK, SimConnect, ReShade or data-source facts.** Write `VERIFY:` next to
  anything unconfirmed and make sure some task confirms it. Facts confirmed in the sim go in a
  spike findings note under `docs/findings/` and are linked from the task.
- **Plans are hypotheses with exit criteria.** If a gate fails, stop and record it; don't build on it.
- **Decisions belong to the user.** Agents gather options and evidence and write a `proposed` ADR.
- **Data licensing:** keep source attribution (OSM is ODbL). Don't redistribute raw inventory data
  until the license audit task says it's fine.
- **No secrets in the repo.** API keys go in environment variables or the environment's secret store.

---

## 11. End of every session (do not skip)

1. Task file: status set, Log updated, acceptance boxes ticked as far as they're true.
2. Write `tracking/logs/YYYY-MM-DD-<who>-<slug>.md` from the template, ending with exact next steps.
3. Commit with the conventions above and push your branch.
4. On `main` only: regenerate the board and update `STATUS.md`.

`/handoff` (`.claude/skills/handoff/SKILL.md`) runs this checklist.
