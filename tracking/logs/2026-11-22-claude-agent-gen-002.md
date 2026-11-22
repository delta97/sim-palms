# Session log: 2026-11-22, claude-agent, gen-002

- **Started / ended:** 2026-11-22 (local)
- **Agent / model / person:** claude-agent (Claude Haiku 5.5)
- **Branch / worktree:** task/gen-002-deterministic-guids-and-per-palm-hashes, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/GEN-002
- **Tasks:** GEN-002 (in_progress -> review)

## Goal

Deterministic GUIDs and per-palm hashes for palmgen, built over palmcore.ids (ARCH-006).

## What changed

- `palmgen/ids.py`: new. GUID_SCHEME "v1"; polygon_name/object_name (name strings); polygon_guid, object_guid, tile_guid, child_guid (UUIDv5 via palmcore.ids.object_guid); format_guid (validates style, delegates to palmcore); unit_hash (palmcore.stable_unit_float).
- `tests/unit/palmgen/test_ids.py`: new. 22 tests, including golden GUID and unit_hash literals.
- `tracking/tasks/GEN-002.md`: acceptance boxes ticked, log entries.

## Verification

- `pytest tests/unit/palmgen/test_ids.py -q`: 22 passed.
- `pytest -q` (full): 277 passed.
- `ruff check .`: clean. `ruff format --check .`: clean. `mypy`: no issues in 18 files.

## Decisions and findings

- The plan's literal name strings (`gen/v1/obj/...`) are not passed to the UUIDv5 helper. The brief requires palmcore helpers, so each GUID is `palmcore.object_guid(kind, GUID_SCHEME, ...)` with structured parts. The GUIDs therefore differ from what the plan's name strings would produce.
- `unit_hash` uses `palmcore.stable_unit_float(purpose, palm_id)` (sha256 of `purpose|palm_id`, 52 bits), not the plan's sha256 of `purpose:palm_id` read as 64 bits. Both are in [0, 1).
- The plan text was not edited. An ARCH or integrator decision is needed on which derivation is canonical before any package is built.

## Open issues

- Decide the canonical GUID and unit_hash derivation (plan vs palmcore) and update `plans/detailed/04-fs2024-integration.md` GEN deterministic ids section to match.
- The Scenery Editor GUID style remains unconfirmed (SPIKE-003). All four styles are supported.

## Handoff: next steps

1. Integrator review of the derivation question above (task GEN-002 Log).
2. If the palmcore derivation is accepted, update the plan section and merge GEN-002. Downstream GEN-003 onward uses `palmgen.ids`.
