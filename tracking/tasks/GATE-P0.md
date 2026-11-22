---
id: GATE-P0
title: "Phase 0 exit gate: one blob cut and replaced, command-line build works"
status: todo
phase: 0
area: GATE
kind: gate
plan_ref: "plans/detailed/05-phases.md#phase-0-feasibility-spike"
depends_on: [DEC-004, RISK-005, SPIKE-001, SPIKE-002, SPIKE-003, SPIKE-004, SPIKE-005, SPIKE-006, SPIKE-007, SPIKE-008, SPIKE-009, SPIKE-010, SPIKE-011]
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

The user confirms that the core trick works on the current sim update: one photogrammetry palm blob is cut with Exclude TIN, a stand-in tree stands in the hole, and the package builds from the command line. Passing unlocks every `windows-sim` task in Phases 1-2 and the phase exits after it.

## Context

- Exit criteria: `plans/05-phases.md` Phase 0; breakdown `plans/detailed/05-phases.md#phase-0-feasibility-spike`.
- Linux code tasks already run in parallel with Phase 0 (ADR-0013). This gate stops sim work and later phase exits, not Linux coding.
- Kill criterion K1 (`plans/detailed/07-risks-and-open-questions.md#kill-criteria`).
- Sign-off: the user. An agent prepares the evidence list below; it never ticks a box without a linked finding.
- After a pass, RISK-006 (risk review after Phase 0) becomes ready.

## Steps

1. Check every `depends_on` task is `done`: `python3 scripts/tasks.py show GATE-P0`.
2. Fill in the Evidence list with links.
3. Walk the exit criteria with the user, one at a time; tick only what the evidence shows.
4. User decides: pass, or fail with the reason.
5. Pass: `python3 scripts/tasks.py set GATE-P0 done --by user --note "<one line>"`.
6. Fail: follow "On fail" below and log it.

## Acceptance criteria

Exit criteria (all must hold):

- [ ] One blob removed cleanly: in `docs/findings/SPIKE-002.md`, TIN + vegetation exclude removes the blob at street level and 300 m (K1 verdict "yes").
- [ ] No autogen trees inside the cut with the vegetation exclude on (SPIKE-002).
- [ ] A stand-in tree is placed in the hole, base on the ground or within about 0.5 m (SPIKE-006), with its GUID recorded.
- [ ] A command-line `fspackagetool` build of the spike project exits 0 and produces a BGL (SPIKE-004).
- [ ] 1,000-polygon build times are recorded (3 runs) and the sim-open behaviour is known (SPIKE-004).
- [ ] All 8 captured XML files and `CAPTURE_NOTES.md` exist in `palmgen/templates/captured/` (SPIKE-003).
- [ ] SimConnect disconnect and crash behaviour is recorded, whatever the result (SPIKE-005).
- [ ] The wall test result is recorded (SPIKE-007).
- [ ] ADR-0014 go/no-go is `accepted` with "Go" or "Go with changes" (SPIKE-011).

## Evidence

Fill in links (file paths or commit shas):

- Findings summary: `docs/findings/SPIKE-010.md`
- Single-blob cut: `docs/findings/SPIKE-002.md`
- Stand-in tree: `docs/findings/SPIKE-006.md`
- Wall test: `docs/findings/SPIKE-007.md`
- Templates: `palmgen/templates/captured/CAPTURE_NOTES.md`
- CLI builds: `docs/findings/SPIKE-004.md`
- SimConnect: `docs/findings/SPIKE-005.md`
- Decision: `tracking/decisions/ADR-0014-phase-0-go-no-go.md`
- Exclusion bug status at gate time: `tracking/logs/sim-update-watch.md`
- Sim version / SDK version at sign-off:

## On fail

- **Exclude TIN or the vegetation exclude doesn't remove the blob (K1):** pause the project. File or upvote a DevSupport bug and link it here. Keep all code. RISK-005 watches for a fix; rerun SPIKE-002 (and this gate) on each sim update. Linux tasks may continue per ADR-0013, but nothing `windows-sim` starts.
- **Command-line build fails but the editor build works:** don't pass. Record the error, check the Package Tool docs and DevSupport, and create a SPIKE task for a workaround (for example building from the Project Editor only). GEN-013 cannot be finished without this.
- **Stand-in tree can't be placed or floats badly:** pass only if a different library object works; else record and treat as R-17 evidence for Phase 2.
- **SimConnect objects don't spawn or leak:** not a gate failure. It is recorded and weakens live placement (DEC-007).

## Verification

```bash
python3 scripts/tasks.py show GATE-P0
grep -E "Status:\*\* accepted" tracking/decisions/ADR-0014-phase-0-go-no-go.md
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [bootstrap] Anchor stub created.
- 2026-11-22 [plan-breakdown] Stub detailed.
