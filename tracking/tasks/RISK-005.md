---
id: RISK-005
title: Set up the sim/SDK update watch and do the first pass on exclusion bugs
status: review
phase: 0
area: RISK
kind: research
plan_ref: "plans/detailed/07-risks-and-open-questions.md#sim-update-watch"
depends_on: []
requires: [network]
agent: msfs-sdk-specialist
estimate_h: 3
touches: [docs/process/sim-update-watch.md, tracking/logs/sim-update-watch.md]
owner: claude-agent
branch: task/risk-005-set-up-the-sim-sdk-update-watch-and-do-t
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/RISK-005"
updated: 2026-11-22
---

## Goal

A short written process says where to look for MSFS 2024 sim and SDK changes, how often, and which findings trigger the TEST-104 regression routine. A watch log exists, and its first entry records the current sim and SDK versions and the status of known exclusion bugs, before Phase 0 testing starts.

## Context

- Risks covered: R-01 (Exclude TIN broken), R-16 (photogrammetry refresh), R-18 (toolchain drift) in `plans/detailed/07-risks-and-open-questions.md#risk-register`.
- TEST-104 owns the regression routine and its own regression log. This task only decides when to run it. Do not duplicate TEST-104's checks; refer to it by id.
- Known thread: DevSupport "SU6 beta: exclusions of any type not working" `https://devsupport.flightsimulator.com/t/su6-beta-exclusions-of-any-type-not-working-rectangle-water-etc/18156`.
- SDK docs: `https://docs.flightsimulator.com/msfs2024/html/` (release notes section; VERIFY exact path).
- Kill criteria K1 and K9 in the detailed plan use this log.

## Steps

1. Find and record the sources (URL plus what to look for):
   - MSFS 2024 sim update and beta release notes (official forums / flightsimulator.com news).
   - SDK release notes (SDK docs site).
   - DevSupport categories for scenery / bugs; search terms `exclude TIN`, `exclusion`, `vegetation exclude`, `photogrammetry`.
   - World Update / photogrammetry announcements naming SoCal cities.
2. Write `docs/process/sim-update-watch.md` with sections: Sources, Cadence (check weekly while active; always when the sim or SDK updates; before each GATE), Trigger rules, How to log.
3. Trigger rules (write them exactly):
   - Sim update or SDK update installed → run TEST-104.
   - Beta or release note mentions exclusions, TIN, polygons, vegetation or photogrammetry → run TEST-104 when that build reaches the user's install, and note in the log.
   - New DevSupport report of broken exclusions on the current version → run TEST-104 now.
   - SoCal photogrammetry or World Update affecting a target city → run TEST-104 at affected sites (R-16).
4. Create `tracking/logs/sim-update-watch.md` with a table: date | sim version | SDK version | source checked | finding | trigger fired (yes/no) | TEST-104 run reference.
5. First pass: record the current public sim and SDK version numbers, the status of the SU6 exclusion thread (fixed, open, which version), and any newer exclusion reports. Flag "VERIFY on the user's PC" for the installed version.
6. Add a line in the doc: the risk reviews (RISK-006..008) read this log.

## Acceptance criteria

- [x] `docs/process/sim-update-watch.md` lists at least 4 sources with URLs and the 4 trigger rules above.
- [x] `tracking/logs/sim-update-watch.md` exists with the table header and at least one dated entry.
- [x] The first entry states the status of the SU6 exclusion thread with a link.
- [x] TEST-104 is referenced as the routine that runs on a trigger; no regression steps are copied into this doc.

## Verification

```bash
test -f docs/process/sim-update-watch.md && test -f tracking/logs/sim-update-watch.md && echo ok
grep -c "https://" docs/process/sim-update-watch.md     # expect >= 4
grep -c "TEST-104" docs/process/sim-update-watch.md     # expect >= 1
grep -E "^\| 20[0-9]{2}-" tracking/logs/sim-update-watch.md | head -1   # a dated row
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/risk-005-set-up-the-sim-sdk-update-watch-and-do-t worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/RISK-005
- 2026-11-22 [claude-agent] Verification: files exist; https count >=4 (6 sources); TEST-104 referenced; dated row present. Acceptance ticked. First pass: latest public sim SU7.2 1.9.24.0 (2026-11-05, third party), SDK docs 1.8.2; SU6 thread 18156 tagged fixed (water polygon fix in SU7 beta 1.9.12.0, unconfirmed); installed versions VERIFY on user's PC.
- 2026-11-22 [claude-agent] Status in_progress -> review.
