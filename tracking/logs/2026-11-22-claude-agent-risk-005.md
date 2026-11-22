# Session log: 2026-11-22, claude-agent, risk-005

- **Started / ended:** 2026-11-22
- **Agent / model / person:** claude-agent (msfs-sdk-specialist role)
- **Branch / worktree:** task/risk-005-set-up-the-sim-sdk-update-watch-and-do-t, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/RISK-005
- **Tasks:** RISK-005 (in_progress -> review)

## Goal

Write the sim/SDK update watch process, create the watch log, and record the first pass on exclusion bugs.

## What changed

- `docs/process/sim-update-watch.md`: sources (6 with URLs), cadence, four trigger rules, how to log; defers to TEST-104.
- `tracking/logs/sim-update-watch.md`: table plus first dated entry (2026-11-22).

## Verification

Spec Verification commands run in the worktree; results are in the task Log.

## Decisions and findings

- Latest public sim per third-party tracker: SU7.2 1.9.24.0 (2026-11-05). Public SDK docs latest: SDK Release 1.8.2 (no date shown).
- The SU6 thread (devsupport topic 18156) is tagged `fixed`; staff said the remaining water-polygon part was fixed in SU7 beta 1.9.12.0, unconfirmed by the poster. Opening post says TIN terraforming looks fixed in SU6 beta.
- The old SDK release-notes URL in the task context is a 404; the working path is `docs.flightsimulator.com/msfs2024/retail/introduction/sdk-release-notes/`.
- WebFetch failed on devsupport (certificate error); `curl` plus the Discourse `.json` endpoint worked and was used.
- Long-running "Exclude TIN leaves photogrammetry" thread (7322) was not read in full; status VERIFY. This is the failure mode closest to R-01.
- Nothing here confirms exclusions work on the user's install; only Phase 0 and TEST-104 can.

## Open issues

- Installed sim and SDK versions: VERIFY on the user's PC.
- Official SU7 / SU7.1 / SU7.2 release notes not read; SoCal World Update check not done.
- No scheduled job created; weekly cadence is manual (a recurring reminder could be set up by the user if wanted).

## Handoff: next steps

1. Run the Phase 0 exclusion test on the installed build, then TEST-104 once it exists; fill the pending cell in the watch log.
2. Read topic 7322 in full and the SU7 notes on the next weekly check.
