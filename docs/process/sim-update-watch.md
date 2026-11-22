# Sim and SDK update watch

Purpose: catch MSFS 2024 sim, SDK and photogrammetry changes that can break exclusions or move the blobs, and decide when to run the TEST-104 regression routine. Covers risks R-01 (Exclude TIN or vegetation exclude broken), R-16 (photogrammetry refresh) and R-18 (toolchain drift) in `plans/detailed/07-risks-and-open-questions.md`. Kill criteria K1 and K9 in that plan use the log described below.

This document only decides **when** to run the routine. The regression steps, pass criteria and regression log are the regression routine `tests/regression/ROUTINE.md` and its log `tests/regression/LOG.md` (written by **TEST-015**; **TEST-104** runs it first and records the baseline); do not copy them here.

Every URL below was read on 2026-11-22 unless marked `VERIFY:`.

## Sources

| # | Source | URL | What to look for |
|---|---|---|---|
| 1 | Official sim release notes (one page per update, listed on the index) | https://www.flightsimulator.com/release-notes/ (example: https://www.flightsimulator.com/release-notes-sim-update-6-1-8-14-0-now-available-msfs-2024/) | Sim version number and date; Scenery Editor, TIN, polygon, vegetation, exclusion or photogrammetry items. |
| 2 | Official forum release-note and beta threads | https://forums.flightsimulator.com/ (example: https://forums.flightsimulator.com/t/release-notes-microsoft-flight-simulator-2024-sim-update-6-1-8-14-0/773330) | Beta build numbers (betas appear weeks before release) and the same keywords. VERIFY: the exact category page to bookmark. |
| 3 | SDK release notes (retail and flighting branches; they can differ) | https://docs.flightsimulator.com/msfs2024/retail/introduction/sdk-release-notes/ and https://docs.flightsimulator.com/msfs2024/flighting/introduction/sdk-release-notes/ | Top heading "SDK Release x.y.z"; DevMode > Scenery Editor entries on exclusion rectangles, polygons, TIN, vegetation. The old `.../html/1_Introduction/Release_Notes.htm` path returned 404 on 2026-11-22; use the paths above. The page shows no release dates; VERIFY: dates from the SDK installer or the in-sim SDK version. |
| 4 | DevSupport bug reports, MSFS 2024 | https://devsupport.flightsimulator.com/ (Discourse; append `.json` to a topic URL or use `/search.json?q=` for scripted reads) | Search terms: `exclude TIN`, `exclusion`, `vegetation exclude`, `photogrammetry`, `terraform`. Read the status tag (`fixed`, `bug_logged`, `duplicate`, `obsolete`) and the sim and SDK versions the poster gives. |
| 5 | Weekly briefings, World Update and photogrammetry announcements | https://www.flightsimulator.com/ (news; example: https://www.flightsimulator.com/april-30th-2026-msfs-weekly-briefing/) | World Update or city updates naming Los Angeles, San Diego or other SoCal cities (R-16). |
| 6 | Third-party update tracker (convenience only; confirm against source 1) | https://msfsaddons.com/msfs-2024-updates/ | Table of released versions, dates and beta builds. |

Known thread (R-01): https://devsupport.flightsimulator.com/t/su6-beta-exclusions-of-any-type-not-working-rectangle-water-etc/18156

## Cadence

- Weekly while the project is active.
- Always when the sim or SDK updates on the user's install.
- Before each GATE (GATE-P0 and later).

## Trigger rules

1. Sim update or SDK update installed -> run the regression routine.
2. Beta or release note mentions exclusions, TIN, polygons, vegetation or photogrammetry -> run the regression routine when that build reaches the user's install, and note in the log.
3. New DevSupport report of broken exclusions on the current version -> run the regression routine now.
4. SoCal photogrammetry or World Update affecting a target city -> run the regression routine at affected sites (R-16).

## How to log

Add one row per check, newest at the bottom, to `tracking/logs/sim-update-watch.md` (columns: date | sim version | SDK version | source checked | finding | trigger fired (yes/no) | TEST-104 run reference). Rules:

- Log a row even when nothing changed, so the log shows the watch ran.
- Record version numbers exactly as published, with the source URL. Public version numbers are not the installed version: mark the installed version `VERIFY on the user's PC` until read from the sim (VERIFY: exact menu path).
- If a trigger fired, put the regression-log entry reference (`tests/regression/LOG.md <date> <trigger>`) in the last column, or `pending` until it has run. A failed TEST-104 on exclusions is kill criterion K1 (K9 for an active or released package); say so in the finding.
- Do not call a bug fixed from a staff reply alone; the fix is confirmed only by a passing regression run on the user's install.

The risk reviews (RISK-006..008) read this log.
