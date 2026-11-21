# ADR-0001: File-based task tracking with worktrees for parallel work

- **Status:** proposed
- **Date:** 2026-11-21
- **Decided by:** pending the user's review (set up by the bootstrap session)
- **Task:** INFRA-001

## Context

The project will be worked on by several AI agents and models across sessions, sometimes in parallel, plus the user on a
Windows PC for anything that needs MSFS 2024. Work has to survive the loss of chat history, and parallel work must not
produce constant merge conflicts.

## Options

1. **External tracker (GitHub Issues, Linear, Notion).** Good UI. Agents need tool access and credentials; state lives outside the
   branch, so a task's spec and its code can drift apart.
2. **Files in the repo, one per task, plus a small CLI.** Every agent can read and edit them with no extra access. Spec, status and
   code change together in one PR. Needs discipline about which files are shared.
3. **A single TODO/STATUS file.** Simple, but every parallel branch edits the same file.

## Decision

Option 2. Tasks are `tracking/tasks/<ID>.md` with frontmatter; `scripts/tasks.py` validates, lists ready work, picks conflict-free
batches (by the `touches` paths), and claims tasks. `scripts/wt.sh` creates one worktree per task. Shared files (`STATUS.md`,
`BOARD.md`, `CHANGELOG.md`) are edited only on `main` at integration. Session logs are one file per session, so they never conflict.

## Consequences

- Agents must keep `touches` accurate; the overlap check is only as good as those lists.
- `BOARD.md` is generated; conflicts on it are resolved by regenerating.
- If the user later wants a UI, GitHub Issues can be generated from the task files; the files stay canonical.

## Links

- `AGENTS.md`, `tracking/README.md`, `scripts/tasks.py`, `scripts/wt.sh`
