---
id: ARCH-006
title: "Add deterministic UUIDv5 ids and seeded randomness to palmcore"
status: review
phase: 1
area: ARCH
kind: build
plan_ref: plans/detailed/01-architecture.md#ws4-deterministic-ids
depends_on: [ARCH-001]
requires: [none]
agent: python-architect
estimate_h: 2
touches: [palmcore/ids.py, tests/unit/palmcore/test_ids.py]
owner: claude-agent
branch: task/arch-006-add-deterministic-uuidv5-ids-and-seeded
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ARCH-006"
updated: 2026-11-22
---

## Goal

`palmcore/ids.py`: hash-based `palm_id`s, UUIDv5 object GUIDs, cluster keys and seeded random helpers, all identical across runs, processes and machines. Rebuilds then give the same ids, GUIDs, headings and variant picks (plan 04 §2), which keeps diffs clean and avoids duplicate objects.

## Context

- Signatures, key formats, namespace derivation and recommended GEN usage: plan_ref section WS4.
- The source plan's `palm_id` example `sdc-000123` is sequential. This plan uses `<prefix>-<16 hex>` from a stable key (Q1). The SCAN plan (`plans/detailed/02-detection-pipeline.md`, W9) chooses the stable key and calls `palm_id(prefix, key)`.
- GEN wraps `NAMESPACE`, `object_guid` and `format_guid` in `palmgen/ids.py` (`plans/detailed/04-fs2024-integration.md`, GEN-002).
- `VERIFY:` the GUID spelling in Scenery Editor XML (braces, case) is unknown until SPIKE-003. Implement all four `format_guid` styles. Don't guess which one GEN will use.
- Never use `hash()` (salted per process), `uuid1`, `uuid4` or an unseeded `random`.
- Changing any output later is a MAJOR contract change (WS10). That is why golden vectors are hard-coded.

## Steps

1. Compute `uuid.uuid5(uuid.NAMESPACE_URL, "urn:palmfix:namespace:v1")` once and paste the literal into `NAMESPACE = uuid.UUID("...")`.
2. Implement `PALM_ID_RE`, `ID_PREFIX_RE`, `palm_key`, `location_key`, `palm_id`, `cluster_key`, `object_guid`, `format_guid` (with the `GuidStyle` Literal), `stable_unit_float`, `seeded_rng` and `assert_unique` as specified. Bad input raises `ValueError`. `assert_unique` raises `palmcore.errors.ContractError`.
3. `location_key` formats with `f"{lon:.5f},{lat:.5f}"` and turns `-0.00000` into `0.00000`.
4. Write `tests/unit/palmcore/test_ids.py`:
   - `NAMESPACE` equals the uuid5 computation (catches a typo in the literal);
   - golden vectors, computed once in this task and committed as literals, for:
     - `palm_id("sdc", "src:sd_street_trees:48213")`;
     - `palm_id("law", location_key(-118.49012, 34.01234))`;
     - `object_guid("polygon", "san-diego-coastal", "tile_a", "cluster:sdc-0000000000000001", "0")`;
     - that GUID in all four `format_guid` styles;
     - `stable_unit_float("heading", "sdc-0000000000000001")`;
     - the first `seeded_rng("variant", "sdc-0000000000000001").random()`;
   - `palm_key` returns `"src:" + min(ids)` regardless of order, and returns the fallback when there are no ids; an empty fallback raises;
   - `cluster_key` ignores order and duplicates; empty input raises;
   - `object_guid` rejects `|` in a part, a bad `kind`, and a call with no parts;
   - every generated `palm_id` matches `PALM_ID_RE`;
   - 100,000 distinct keys give 100,000 distinct `palm_id`s;
   - `stable_unit_float` stays within [0, 1) over 10,000 inputs;
   - a subprocess (`sys.executable -c ...`) gives the same `palm_id` as the test process.
5. Run the Verification commands.

## Acceptance criteria

- [x] All names and signatures match WS4.
- [x] Golden vectors are committed and pass.
- [x] The module never uses `hash()`, `uuid1`, `uuid4` or an unseeded `random`.
- [x] ruff, mypy (strict for palmcore) and pytest are green.

## Verification

```bash
pytest tests/unit/palmcore/test_ids.py -q
python -c "from palmcore.ids import palm_id; print(palm_id('sdc', 'src:sd_street_trees:48213'))"   # same value on every run and machine
ruff check palmcore tests && mypy
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/arch-006-add-deterministic-uuidv5-ids-and-seeded worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ARCH-006
- 2026-11-22 [claude-agent] Implemented palmcore/ids.py (NAMESPACE=1e4715d1-de00-51bf-a07a-679b67048e4f). Note: location_key uses the 'loc:' prefix from plan_ref WS4; task Step 3 omits it. Followed WS4. Flag for reviewer.
- 2026-11-22 [claude-agent] Tests: tests/unit/palmcore/test_ids.py 28 passed (golden vectors, subprocess determinism, 100k uniqueness, AST check for hash/uuid1/uuid4/unseeded random). Full suite 51 passed.
- 2026-11-22 [claude-agent] ruff check palmcore tests: clean; ruff format --check: clean; mypy (strict palmcore): no issues in 6 source files.
- 2026-11-22 [claude-agent] Acceptance ticked: signatures match WS4 (ids.py); golden vectors pass (28 tests); AST test finds no hash/uuid1/uuid4/unseeded random calls; ruff/mypy/pytest green.
- 2026-11-22 [claude-agent] Status in_progress -> review.
