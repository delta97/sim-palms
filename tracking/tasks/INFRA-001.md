---
id: INFRA-001
title: Bootstrap plans, tracking, worktree tooling and specialist agents
status: review
phase: 0
area: INFRA
kind: build
plan_ref: tracking/README.md
depends_on: []
requires: [none]
agent: task-planner
estimate_h: 4
touches: [plans/README.md, tracking/README.md, tracking/tasks/_TEMPLATE.md, tracking/logs/_TEMPLATE.md, tracking/decisions/_TEMPLATE.md, tracking/decisions/ADR-0001-repository-and-tracking-structure.md, scripts/tasks.py, scripts/wt.sh, AGENTS.md, CLAUDE.md, README.md, CHANGELOG.md, .claude/agents/, .claude/skills/, .github/workflows/tracking.yml, .gitignore, docs/findings/README.md]
owner: bootstrap-session
branch: claude/eloquent-brahmagupta-gv5mbg
worktree: ""
updated: 2026-11-22
---

## Goal

Put the original plan set in the repo, break each plan file into executable detail and task files, and set up the
infrastructure for parallel, multi-agent, multi-session work with durable logs.

## Context

Source: the user's `Palm_Photogrammetry_MSFS2024.zip` (2026-11-21). Its nested `msfs-palm-fix-plan.zip` was a byte-identical
copy of the same nine Markdown files and was not added. Decision record: `tracking/decisions/ADR-0001-repository-and-tracking-structure.md`.

## Steps

1. Copy the nine plan files to `plans/`.
2. Create the task format, `scripts/tasks.py`, anchor stubs for cross-area ids, and `scripts/wt.sh`.
3. Detail each plan file into `plans/detailed/` plus task files (one subagent per plan file).
4. Write `AGENTS.md`, `CLAUDE.md`, tracking docs, specialist agents, skills, CI validation.

## Acceptance criteria

- [x] `plans/` holds the original files unchanged.
- [x] `python3 scripts/tasks.py validate` reports 0 errors.
- [x] `scripts/wt.sh new/list/remove` tested in a scratch clone.
- [ ] The user has reviewed ADR-0001 and the agent roster.

## Verification

```bash
python3 scripts/tasks.py validate
python3 scripts/tasks.py ready --requires none
diff -r <unzipped-source-folder> plans/ --exclude=detailed --exclude=msfs-palm-fix-plan.zip
```

## Log

- 2026-11-21 [bootstrap-session] Task created and executed; worktree helper tested in a scratch clone (claim commit, worktree add, double-claim refused, remove).
- 2026-11-22 [bootstrap-session] PR opened: https://github.com/delta97/sim-palms/pull/1
