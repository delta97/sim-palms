# Status

**Updated:** 2026-11-22 · **Phase:** 0 (not started) · **Newest log:** [2026-11-22 bootstrap](logs/2026-11-22-bootstrap-plans-and-tracking.md)

## Where things stand

- Planning is complete: 8 detailed plans, 213 tasks, 0 validation errors, 0 unordered conflicts. Board: [BOARD.md](BOARD.md).
- Nothing is built yet. No sim, SDK or data-source fact in the plans is confirmed; unconfirmed items are marked `VERIFY:`.
- Policy (proposed, [ADR-0013](decisions/ADR-0013-linux-code-work-in-parallel-with-phase-0.md)): Linux code work runs in parallel with Phase 0; sim work and phase exits follow the gates.

## Ready now

| For agents (Linux) | For the user |
|---|---|
| ARCH-001 scaffold (unlocks most of Phase 1-2 code) | DEC-004 pick the first test block (blocks Phase 0 testing) |
| SPIKE-009 SimConnect spike console app | SPIKE-001 install the SDK, empty Dev Mode project |
| | TEST-006 verify a repeatable flight/camera/screenshot method |
| | RISK-003 other palm/tree mods to mask |

## Waiting on the user

1. **Review** ADR-0001 (tracking structure) and ADR-0013 (parallel code during Phase 0). Both are `proposed`.
2. **DEC-004:** which street is the first test block.
3. **Public or private repo?** Affects DEC-001, DEC-004 (naming a street you know), DEC-008 (asset storage) and RISK-002.
4. **DEC-008:** Git LFS or external storage for Blender files, textures and screenshots (needed before Phase 3 and the first visual runs).

## Next

1. An agent claims ARCH-001 (`/start-task ARCH-001`).
2. The user does DEC-004, then SPIKE-001 on the sim PC.
