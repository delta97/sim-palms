---
id: REGION-050
title: "Florida regions after the Florida species set exists (placeholder)"
status: todo
phase: 6
area: REGION
kind: build
plan_ref: "plans/detailed/05-phases.md#per-region-task-pattern"
depends_on: [GATE-P6, DEC-011, ASSET-065]
requires: [network, windows-sim, human]
agent: task-planner
estimate_h: 16
touches: [tracking/logs/REGION-050.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

Coarse placeholder. Scope: Florida photogrammetry cities (for example Miami; the list comes from ADR-0012), only if DEC-011 puts Florida in scope and the Florida species set (ASSET-060..065) is accepted. Two regions at about 8 h each. When this task becomes ready, it is split into one set of five tasks per region (config, masks, palmscan + QA, build + spot checks, perf) following the per-region pattern, and then set to `dropped` with a note naming the new ids.

## Context

- Pattern: `plans/detailed/05-phases.md#per-region-task-pattern`; commands: `docs/regions/RUNBOOK.md` (REGION-001).
- Order and scope: ADR-0012 (DEC-011). Plan 05 order: San Diego coastal, LA Westside and beaches, rest of LA basin, other SoCal photogrammetry cities; Florida after the Florida species set exists.
- Waits for GATE-P6 so the pattern is proven on two regions before it is repeated.
- Before the first Florida region, the palm genus list and species aliases need Florida genera (Sabal, Roystonea, Cocos, Wodyetia and others). No SCAN task exists for this yet: create one (`python3 scripts/tasks.py new SCAN --title "Add Florida genera and aliases" --phase 6`) and add it to this task's `depends_on`.
- Florida inventories are different sources; each needs an adapter check (RISK-001 for licenses).
- If DEC-011 leaves Florida out, set this task to `dropped`.

## Steps

1. Read ADR-0012 and list the regions in scope for this placeholder, each with a slug and a starting bbox.
2. For each region, create five tasks with `python3 scripts/tasks.py new REGION --title "<Region>: <step>" --phase 6`, copying the structure of REGION-010..014 (ids in a fresh block, for example REGION-0N0..0N4). Set `touches` to that region's own files only.
3. Write the split (region, slug, bbox, new ids) into `tracking/logs/REGION-050.md`.
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
