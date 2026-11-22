# ADR-0013: Allow Linux-container code work to run in parallel with Phase 0

- **Status:** proposed
- **Date:** 2026-11-22
- **Decided by:** pending the user's review (set as the default by the bootstrap session)
- **Task:** INFRA-001

## Context

`plans/05-phases.md` says Phase 0 proves the core trick (Exclude TIN on the current sim update) "before anything else gets built".
Phase 0 is almost entirely `windows-sim` + `human` work that only the user can do on their PC. If every code task waited for
`GATE-P0`, cloud and Linux agents would sit idle for the whole of Phase 0.

## Options

1. **Strict:** all build tasks wait for `GATE-P0`. Nothing is wasted on a no-go, but agents are idle.
2. **Parallel code, gated integration:** tasks with `requires: [none]` or `[network]` (scaffold, schemas, adapters on fixtures,
   geometry, XML writer against placeholder templates) may start now. Anything needing the sim, and every phase exit, still waits
   for its gate and SPIKE outputs.

## Decision

Option 2 as the default. `ARCH-001` no longer depends on `GATE-P0`. Code that depends on Phase 0 facts (for example the XML writer
needing captured templates) still depends on the SPIKE task that captures them.

## Consequences

- If Phase 0 is a no-go, some Linux code is parked rather than discarded. The detection pipeline stays useful for any later fix method.
- To revert to strict: add `GATE-P0` to `depends_on` of `ARCH-001` and run `python3 scripts/tasks.py validate`.

## Links

- `plans/05-phases.md`, `plans/detailed/05-phases.md` (Parallel tracks), `tracking/tasks/ARCH-001.md`
