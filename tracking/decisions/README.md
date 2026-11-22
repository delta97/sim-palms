# Decisions

Architecture decision records. File name: `ADR-NNNN-<slug>.md`, numbered in order. Template: `_TEMPLATE.md`.

- Agents write ADRs with **Status: proposed**. Only the user moves one to **accepted** or **rejected**.
- An accepted ADR that changes scope must list the tasks it adds, drops or re-scopes, and those task files must be updated in the same PR.
- `DEC-*` tasks in `tracking/tasks/` track the open decisions. Each one ends with an ADR.

| ADR | Title | Status |
|---|---|---|
| [0001](ADR-0001-repository-and-tracking-structure.md) | File-based task tracking with worktrees for parallel work | proposed |
| [0013](ADR-0013-linux-code-work-in-parallel-with-phase-0.md) | Allow Linux-container code work in parallel with Phase 0 | proposed |

ADR-0002 to ADR-0012 are reserved for the DEC tasks (see `plans/detailed/07-risks-and-open-questions.md`). New ADRs start at 0014.
