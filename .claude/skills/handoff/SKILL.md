---
name: handoff
description: End-of-session checklist for sim-palms. Updates task status and Logs, writes the session log with exact next steps, commits and pushes, and on main regenerates the board and STATUS.md. Use before stopping work, when context is running low, or when the user says "wrap up" or "handoff".
---

# Handoff

Goal: the next agent can continue from files alone, with no chat history.

1. For each task touched this session:
   - `python3 scripts/tasks.py log <ID> "<what was done, results, commit sha>" --by <you>`
   - Set the true status: `review` if verification passed, `blocked` with a reason, or leave `in_progress` with a Log line saying exactly where you stopped.
   - Tick only the acceptance boxes that are actually met.
2. Write `tracking/logs/YYYY-MM-DD-<who>-<slug>.md` from `tracking/logs/_TEMPLATE.md`:
   files changed (with commit shas), verification commands and result lines, findings and decisions, open issues
   (with task ids, creating tasks with `python3 scripts/tasks.py new` where needed), and numbered next steps.
3. `python3 scripts/tasks.py validate` must pass.
4. Commit: `<area>(<ID>): <summary>` plus a `Task: <ID>` trailer; tracking-only changes as `chore(tracking): ...`. Push the branch.
5. Only if on `main` (the integration branch): `python3 scripts/tasks.py board`, update `tracking/STATUS.md`
   (phase, in flight, blocked on the user, newest log link, date), add `CHANGELOG.md` lines for merged tasks, commit and push.
6. Reply to the user with: what's done, what's in review, what's blocked on them, and the next step.
