# CLAUDE.md

@AGENTS.md

## Claude Code specifics

- Start every session with the checklist in AGENTS.md section 2. `/start-task <ID>` does it for a named task.
- For parallel work, use `/plan-batch`: it picks a conflict-free batch with `scripts/tasks.py batch`,
  creates one worktree per task with `scripts/wt.sh new`, and launches the matching specialist from
  `.claude/agents/` in each worktree. Subagents must be told their worktree path and task id.
- Subagents do not commit to `main` and do not touch `tracking/STATUS.md`, `tracking/BOARD.md` or `CHANGELOG.md`.
  The parent session integrates.
- End every session with `/handoff`.
- Keep model identifiers out of commits, code and docs.
