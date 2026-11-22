---
id: AREA-000
title: Short imperative title
status: todo
phase: 0
area: AREA
kind: build
plan_ref: plans/detailed/NN-name.md#section
depends_on: []
requires: [none]
agent: general-purpose
estimate_h: 2
touches: []
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

<!--
FIELD REFERENCE (do not copy this comment into real task files)

id          AREA-NNN. 001-099 = ordinary tasks, 100-199 = deliverable/interface anchors
            that other areas depend on. GATE-P<n> = phase exit gates. Never reuse an id.
status      todo | in_progress | blocked | review | done | dropped
            ("ready" is computed: status=todo and every depends_on is done)
phase       0-7, matching plans/05-phases.md
area        ARCH SCAN GEN LIVE ASSET SPIKE TEST DEC RISK FX REGION GATE INFRA
kind        build | spike | research | decision | test | doc | gate
plan_ref    path#anchor of the detailed plan section this task implements
depends_on  [IDS] that must be done first. Keep it minimal and real.
requires    environment the task needs; any of:
              none        runs in any Linux container (cloud agents can do it)
              windows-sim needs the Windows PC with MSFS 2024 + SDK installed
              blender     needs Blender + the MSFS 2024 glTF exporter
              gpu         needs a local GPU (inference, perf captures)
              network     needs live internet data pulls (APIs, S3 LiDAR)
              human       needs a human judgement, purchase or decision
agent       suggested .claude/agents/<name> to run it
estimate_h  rough hours
touches     repo paths (files or dir/) this task will create or modify. Used to detect
            conflicts between tasks running in parallel. Be specific.
owner       who claimed it (session id, agent name or person). Empty when unclaimed.
branch      git branch the work happens on
worktree    worktree path, if one is used
updated     YYYY-MM-DD of the last edit to this file
issue       (optional) GitHub issue number mirroring this task; filled in by scripts/issues.py.
            New tasks get an issue automatically when they reach main (see AGENTS.md 5a).
-->

## Goal

One or two sentences: what exists when this is done, and why it matters.

## Context

What the executor needs to know that is not obvious from the plan_ref. Links to
plans, decisions (tracking/decisions/ADR-*.md) and related tasks.

## Steps

1. Concrete, ordered steps. Name files, functions, CLI flags.

## Acceptance criteria

- [ ] Observable, checkable outcomes. Each one should be verifiable by a reviewer.

## Verification

Commands to run or checks to perform, with the expected result.

```bash
pytest tests/unit/test_example.py -q
```

## Log

<!-- Append-only. Newest last. Format: - YYYY-MM-DD [who] what happened (commit sha if any) -->
- 2026-11-21 [plan-breakdown] Task created.
