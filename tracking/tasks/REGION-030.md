---
id: REGION-030
title: "Rest of LA basin: split into regions and run the per-region pattern (placeholder)"
status: todo
phase: 6
area: REGION
kind: build
plan_ref: "plans/detailed/05-phases.md#per-region-task-pattern"
depends_on: [GATE-P6, DEC-011]
requires: [network, windows-sim, human]
agent: task-planner
estimate_h: 24
touches: [tracking/logs/REGION-030.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Coarse placeholder. Scope: The rest of the LA basin outside `la-westside` (for example downtown, Hollywood, the South Bay, Long Beach, the San Fernando Valley; the actual list comes from ADR-0012). At 5-10 h per region (plan 05) and roughly three sub-regions, about 24 h. When this task becomes ready, it is split into one set of five tasks per region (config, masks, palmscan + QA, build + spot checks, perf) following the per-region pattern, and then set to `dropped` with a note naming the new ids.

## Context

- Pattern: `plans/detailed/05-phases.md#per-region-task-pattern`; commands: `docs/regions/RUNBOOK.md` (REGION-001).
- Order and scope: ADR-0012 (DEC-011). Plan 05 order: San Diego coastal, LA Westside and beaches, rest of LA basin, other SoCal photogrammetry cities; Florida after the Florida species set exists.
- Waits for GATE-P6 so the pattern is proven on two regions before it is repeated.
- Each sub-region must not overlap `la-westside` or each other (plan 01 Q7); share edges along streets, or `mask_out` neighbours.
- Inventory: the LA County compilation covers many cities; check per city in the ARCH-008 and RISK-001 notes.
- Known LA mods (RISK-003) apply here too.

## Steps

1. Read ADR-0012 and list the regions in scope for this placeholder, each with a slug and a starting bbox.
2. For each region, create five tasks with `python3 scripts/tasks.py new REGION --title "<Region>: <step>" --phase 6`, copying the structure of REGION-010..014 (ids in a fresh block, for example REGION-0N0..0N4). Set `touches` to that region's own files only.
3. Write the split (region, slug, bbox, new ids) into `tracking/logs/REGION-030.md`.
4. Run `python3 scripts/tasks.py validate` and `python3 scripts/tasks.py conflicts`; fix any conflict among the new tasks.
5. Set this task to `dropped` with `--note "split into <ids>"`.

## Acceptance criteria

- [ ] Every region in scope has five tasks following the pattern.
- [ ] No new task overlaps another region's files or bbox.
- [ ] This placeholder is `dropped` with the new ids in its note.

## Verification

```bash
python3 scripts/tasks.py list --area REGION
python3 scripts/tasks.py validate && python3 scripts/tasks.py conflicts
```

## Log

- 2026-11-22 [plan-breakdown] Task created.
