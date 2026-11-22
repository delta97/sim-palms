---
name: plan-batch
description: Run several sim-palms tasks in parallel safely. Picks a conflict-free batch of ready tasks, creates one git worktree per task, launches the matching specialist subagent in each, then reviews and integrates. Use when the user asks to parallelise work or "run the next batch".
---

# Parallel batch

Arguments (optional): max tasks (default 3), allowed environments (default `none`; add `network` if this machine can reach data sources).

1. Plan:
   - `python3 scripts/tasks.py validate`
   - `python3 scripts/tasks.py batch --requires <envs> --max <n>`
   - Show the batch to the user: id, title, agent, estimate. Proceed unless the user asked to approve first.
2. Set up, one task at a time (each claim is its own commit on the integration branch):
   - `scripts/wt.sh new <ID> --owner <agent-name>-<n>` (add `--push` if other machines or sessions are working).
   - In a cloud session that can only push one assigned branch, don't use worktrees for pushing: run the batch
     sequentially on that branch, or keep worktree branches local and merge them back before pushing.
3. Launch one subagent per task, all in a single message so they run concurrently. Use the task's `agent` field
   as the subagent type. The prompt must include: the task id, the absolute worktree path, "work only inside this path",
   "follow AGENTS.md section 3 and the protocol in your agent file", and "do not edit STATUS.md, BOARD.md or CHANGELOG.md".
4. As each finishes: run the `code-reviewer` agent on that worktree. If approved, merge the task branch into the
   integration branch, `python3 scripts/tasks.py set <ID> done --by <you>`, add the CHANGELOG line, and
   `scripts/wt.sh remove <ID> --delete-branch`. If changes are requested, send them back to the same subagent.
5. After the batch: `python3 scripts/tasks.py board`, update `tracking/STATUS.md`, write one session log covering the
   batch, commit, push. Then report: merged, in review, blocked, and the next batch `tasks.py batch` would pick.
