---
name: start-task
description: Start or resume work on a sim-palms task by id. Reads status and the last handoff, checks the task is ready, claims it, and loads its spec. Use when the user says "start/resume/work on <TASK-ID>" or at the start of a session.
---

# Start a task

Argument: a task id such as `SCAN-003`. If none is given, pick one with `python3 scripts/tasks.py ready --requires none`
and tell the user which one and why.

1. Orient:
   - Read `tracking/STATUS.md` and the newest file in `tracking/logs/`.
   - `python3 scripts/tasks.py validate` (report errors; don't proceed on a broken tracker).
2. Check the task: `python3 scripts/tasks.py show <ID>`.
   - Status `in_progress` with another owner: stop and ask the user.
   - Status `in_progress` with you or this branch as owner, or `blocked`: you are resuming. Read its Log to the end.
   - Not ready (open dependencies): report them and suggest a ready alternative.
   - `requires` includes something this environment lacks (windows-sim, blender, gpu, human): prepare the runbook or brief
     the task asks for and say what the user must do. Don't fake the result.
3. Claim it if it is `todo`:
   - Parallel work on one machine: `scripts/wt.sh new <ID> --owner <you> --push`, then work in the printed worktree path.
   - Single checkout or a cloud session pinned to a branch: `python3 scripts/tasks.py claim <ID> --owner <you> --branch "$(git rev-parse --abbrev-ref HEAD)"`.
4. Read the `plan_ref` section, and any ADRs or findings notes the task links.
5. Tell the user in 3-5 lines: the goal, the first steps you'll take, anything that needs them.
6. Work, following AGENTS.md section 3. Use the specialist named in the task's `agent` field if delegating.
