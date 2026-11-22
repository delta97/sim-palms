---
id: ASSET-016
title: "Mexican fan palm: fix pass, acceptance sign-off and pipeline lessons"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w9-mexican-fan-palm-first"
depends_on: [ASSET-015, DEC-002]
requires: [blender, windows-sim, human]
agent: asset-pipeline-artist
estimate_h: 4
touches: [assets/blender/washingtonia_robusta/, assets/PackageSources/modelLib/washingtonia_robusta/, assets/species/washingtonia_robusta.yaml, assets/manifest.json, assets/reviews/washingtonia_robusta.md, tests/visual/lineup-washingtonia_robusta/, assets/TOOLCHAIN.md, assets/budgets.yaml, plans/detailed/03-palm-assets.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

All P1 fixes from the ASSET-015 review are done, robusta passes the full acceptance checklist and is `accepted`, and the lessons are written into the plan, TOOLCHAIN.md and budgets.yaml. The other four species then start from a proven pipeline.

## Context

- Input: the fix list in `assets/reviews/washingtonia_robusta.md`. P2 items are optional if they take less than about 1 h each. Turn P3 items into new tasks if they're worth doing (`python3 scripts/tasks.py new ASSET --title ...`).
- DEC-002 (ADR-0003, build or license) is decided before this task, informed by the pilot hours. Add its one-line `Decided (ADR-0003): ...` note to the W1 build-vs-license section of `plans/detailed/03-palm-assets.md`, and apply its Consequences to the remaining species tasks (licensed species: re-scope their Steps or create the conversion tasks ADR-0003 names).
- Lessons go in `plans/detailed/03-palm-assets.md`: update the W4/W6/W7/W8 sections where the review showed the plan was wrong (for example LOD switch values, alpha cutoff, texture sizes). Keep each change small and dated in the Log.
- If the fix work exceeds about 4 h, stop, log it, and split the remainder into a new task rather than going over.

## Steps

1. Fix all P1 items in Blender, then re-export the affected variants and LODs.
2. Tune the LOD switch values (if the exporter exposes them) so the switches land near the design distances, based on the distances measured in ASSET-015.
3. Rebuild the package, re-run the lineup screenshots for the views that had issues, and add them to the same lineup folder under a new date.
4. Re-run the W11 checklist. When all items pass, set `status: accepted` in the species yaml.
5. Run `build-manifest` and `validate`, then commit the updated manifest.
6. Write lessons into the plan sections, TOOLCHAIN.md (`## Export settings`, `## Known issues`) and `budgets.yaml` (if thresholds changed).

## Acceptance criteria

- [ ] No open P1 items in the review file, and the checklist is fully ticked by the user (their name or initials on the sign-off line).
- [ ] `assets/species/washingtonia_robusta.yaml` has `status: accepted`, and the manifest reflects it.
- [ ] `check`, `build-manifest --check` and `validate` all exit 0.
- [ ] `plans/detailed/03-palm-assets.md` carries the `Decided (ADR-0003)` note.
- [ ] The plan, TOOLCHAIN.md and budgets.yaml changes are listed in the Log.

## Verification

```bash
python -m palmcore.assets check --species washingtonia_robusta; echo $?   # 0
python -m palmcore.assets build-manifest --check; echo $?  # 0
python -m palmcore.assets validate; echo $?                # 0
grep -n 'status: accepted' assets/species/washingtonia_robusta.yaml
```
Manual: the user reviews the new lineup screenshots and signs off in `assets/reviews/washingtonia_robusta.md`.

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Added depends_on DEC-002: DEC-002 must be decided before modeling beyond the pilot, and this task writes the 'Decided (ADR-0003)' note into plans/detailed/03-palm-assets.md (DEC-002 no longer edits that plan). Cross-area reconciliation.
