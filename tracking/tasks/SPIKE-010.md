---
id: SPIKE-010
title: Write the one-page Phase 0 findings note with screenshots
status: todo
phase: 0
area: SPIKE
kind: doc
plan_ref: "plans/detailed/05-phases.md#phase-0-feasibility-spike"
depends_on: [SPIKE-002, SPIKE-003, SPIKE-004, SPIKE-005, SPIKE-006, SPIKE-007]
requires: [none]
agent: msfs-sdk-specialist
estimate_h: 1.5
touches: [docs/findings/SPIKE-010.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

One page that answers the six Phase 0 questions directly, with the key screenshots inline, so the user can make the go/no-go call in five minutes without reading every spike note.

## Context

- Phase 0 deliverable "a one-page findings note with screenshots" and the questions table in `plans/05-phases.md` Phase 0.
- Sources: `docs/findings/SPIKE-001.md` to `SPIKE-007.md`, `palmgen/templates/captured/CAPTURE_NOTES.md`, `docs/findings/TEST-006.md` if done, and RISK-005's watch log (`tracking/logs/sim-update-watch.md`) for known exclusion bugs.
- Link screenshots from the spike folders (`docs/findings/SPIKE-00N/...`); don't copy them.
- Write for a reader with no context. Short sections, a Summary and a Recap.

## Steps

1. Read every source note. List any question a spike left unanswered; if one is essential, set this task `blocked` and name the spike that must be rerun.
2. Write `docs/findings/SPIKE-010.md`:
   - Summary (3-5 bullets): versions tested, K1 verdict, biggest surprise.
   - Answers table: the six Phase 0 questions (Exclude TIN works?; what's under the cut at street level and 300 m; autogen trees in the hole and does vegetation exclude stop them; 1,000-polygon build time; builds with the sim open; SimConnect objects after disconnect), each with a one-line answer and a link to the evidence.
   - Exit criteria: one blob removed cleanly; stand-in tree placed; command-line build working. Each met / not met with evidence link.
   - Screenshots: before and after (SPIKE-002), stand-in (SPIKE-006), wall test (SPIKE-007), inline as Markdown images.
   - Design consequences: one line each for GEN (templates, clipping buffer, build-with-sim-open), LIVE (cleanup logic), TEST (regression project path `spikes/palmfix-spike/`).
   - Open `VERIFY:` items left after Phase 0 and the task that now owns each.
   - Recap.
3. Keep it to about one printed page plus images.

## Acceptance criteria

- [ ] Each of the six questions has a direct answer and an evidence link.
- [ ] Each Phase 0 exit criterion is marked met or not met with evidence.
- [ ] At least the before/after screenshots render inline.
- [ ] Remaining `VERIFY:` items each name an owning task id.

## Verification

```bash
test -f docs/findings/SPIKE-010.md
grep -c "](" docs/findings/SPIKE-010.md     # links and images present
grep -oE "docs/findings/SPIKE-00[0-9]/[^)]+" docs/findings/SPIKE-010.md | while read p; do test -e "$p" || echo "missing $p"; done
```

No "missing" lines.

## Log

- 2026-11-22 [plan-breakdown] Task created.
