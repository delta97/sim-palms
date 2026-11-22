---
id: GATE-P5
title: "Phase 5 exit gate: placement method decided with numbers; one-click region switching"
status: todo
phase: 5
area: GATE
kind: gate
plan_ref: "plans/detailed/05-phases.md#phase-5-placement-bake-off-and-companion-app"
depends_on: [GATE-P3, GATE-P4, DEC-005, TEST-103, LIVE-009, DEC-007, DEC-003, LIVE-100, LIVE-101]
requires: [human]
agent: task-planner
estimate_h: 0.5
touches: []
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

The user confirms that static vs live placement is decided from measurements within the agreed performance budget, and that the companion app switches regions with one click and no file copying. Passing starts scale-out (DEC-011 and the REGION tasks depend on this gate).

## Context

- Exit criteria: `plans/05-phases.md` Phase 5; breakdown `plans/detailed/05-phases.md#phase-5-placement-bake-off-and-companion-app`.
- Bake-off spec: `plans/detailed/04-fs2024-integration.md#live-placement-bake-off`. Budget: ADR-0006 (DEC-005). Comparison tool: `python -m tests.perf.compare` (`plans/detailed/06-testing.md#run-comparison`).
- LIVE-101 (live spawner) is `dropped` if DEC-007 picks static; a dropped dependency counts as satisfied. If live wins, LIVE-101's soak test (`python -m tests.perf.soak`) must pass.
- Kill criterion K5 (`plans/detailed/07-risks-and-open-questions.md#kill-criteria`).
- After a pass, RISK-008 (risk review before scale-out) and DEC-011 become ready.
- Sign-off: the user.

## Steps

1. Check every `depends_on` task is `done` or `dropped`.
2. Fill in the Evidence list.
3. Read the bake-off report with the user; then try region switching in the app together (activate, start sim, check, deactivate).
4. User decides. Pass: `python3 scripts/tasks.py set GATE-P5 done --by user`.

## Acceptance criteria

- [ ] The bake-off report covers 3 setups (no fix, static, live) × 3 runs on the TEST-103 route, with average FPS, 1% low, p99 frametime and stutter (LIVE-009).
- [ ] `python -m tests.perf.compare <bakeoff run>` exits 0 for the chosen variant against the ADR-0006 budget (default: ≤ +5% average frametime, no added stutter).
- [ ] ADR-0008 (static or live) is `accepted` with the measurements quoted.
- [ ] ADR-0004 (app language) is `accepted`.
- [ ] LIVE-100: activating and deactivating a region is one action in the app, needs no file copying, and the sim-running warning works.
- [ ] If live placement won: LIVE-101 soak test passes (`soak` exit 0: object count ≤ cap, zero after shutdown, no leftovers after kill + cleanup).

## Evidence

- Bake-off: `tests/perf/bakeoff/<date>/report.md`
- Decisions: `tracking/decisions/ADR-0006-performance-budget.md`, `tracking/decisions/ADR-0008-static-or-live-placement.md`, `tracking/decisions/ADR-0004-companion-app-language.md`
- Region manager check: `tracking/logs/LIVE-100.md`
- Soak (live only): `tests/perf/soak/<date>/report.md`, `tracking/logs/LIVE-101.md`

## On fail

- **Both static and live exceed the budget after LOD tuning (K5):** reduce scope (density cap, smaller regions) or stop scale-out. The user picks; record it in ADR-0008.
- **Results unstable (`compare` exit 3):** rerun the unstable variant (TEST-103 procedure), don't decide on noise.
- **Region switching needs manual steps:** fix in LIVE-003/LIVE-005 and rerun LIVE-100.
- **Live won but the soak test fails:** fall back to static (plan default) unless the fix is small; update ADR-0008.

## Verification

```bash
ls tests/perf/bakeoff/
grep -E "Status:\*\* accepted" tracking/decisions/ADR-0008-static-or-live-placement.md tracking/decisions/ADR-0004-companion-app-language.md
python3 scripts/tasks.py show GATE-P5
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
