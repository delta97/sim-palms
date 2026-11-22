# Session log: 2026-11-22, claude-agent, arch-006

- **Started / ended:** 2026-11-22 (local time, not recorded precisely)
- **Agent / model / person:** claude-agent (Haiku 5.5 harness, brief asked for Opus 5.5 trailer)
- **Branch / worktree:** task/arch-006-add-deterministic-uuidv5-ids-and-seeded / C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ARCH-006
- **Tasks:** ARCH-006 (in_progress -> review)

## Goal

Implement `palmcore/ids.py` and its unit tests per plan WS4: UUIDv5 palm ids, object GUIDs, cluster keys and seeded randomness, with golden vectors.

## What changed

- `palmcore/ids.py`: new. NAMESPACE literal, palm_key, location_key, palm_id, cluster_key, object_guid, format_guid (four styles), stable_unit_float, seeded_rng, assert_unique.
- `tests/unit/palmcore/test_ids.py`: new. 28 tests: golden vectors, namespace derivation, key rules, input rejection, 100k uniqueness, [0,1) range, subprocess determinism, AST check against hash/uuid1/uuid4/unseeded random.
- `tracking/tasks/ARCH-006.md`: acceptance boxes ticked, log entries.
- Commit: see git log on the task branch.

## Verification

- `pytest tests/unit/palmcore/test_ids.py -q`: 28 passed. Full suite: 51 passed.
- `python -c "from palmcore.ids import palm_id; ..."`: `sdc-a6924214cef25e3a`
- `ruff check .`, `ruff format --check .`: clean.
- `mypy`: no issues in 6 source files.

## Decisions and findings

- **location_key prefix conflict:** plan_ref WS4 says `f"loc:{lon:.5f},{lat:.5f}"`. Task Step 3 says `f"{lon:.5f},{lat:.5f}"` with no prefix. Implemented the `loc:` form, because the task's Context points to WS4 for key formats and the `src:` and `cluster:` keys carry prefixes. The golden vector `law-a4b4b8ac510054ac` depends on this. Reviewer should confirm, and the spec should be aligned in one place.
- `palm_key` filters out empty strings from stable ids before taking the minimum.
- Golden vectors were computed from this implementation and then frozen. They are a regression guard, not an independent cross-check.

## Open issues

- `VERIFY:` GUID text style for Scenery Editor XML is still unknown (SPIKE-003). All four styles are implemented.

## Handoff: next steps

1. Reviewer: confirm the `loc:` prefix decision above, then review the branch against the acceptance criteria.
2. After merge, the integrator sets ARCH-006 to done and adds the CHANGELOG line.
