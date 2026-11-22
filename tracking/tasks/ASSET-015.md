---
id: ASSET-015
title: "Mexican fan palm: in-sim review (lineup and test neighborhood)"
status: todo
phase: 3
area: ASSET
kind: test
plan_ref: "plans/detailed/03-palm-assets.md#w11-acceptance-review"
depends_on: [ASSET-014, TEST-102]
requires: [windows-sim, human]
agent: asset-pipeline-artist
estimate_h: 3
touches: [assets/reviews/washingtonia_robusta.md, tests/visual/lineup-washingtonia_robusta/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

A documented in-sim review of the three robusta variants, with screenshots, a filled checklist and a prioritized list of fixes. ASSET-016 acts on it before any other species is modeled.

## Context

- Procedure and checklist: `#w11-acceptance-review`. Screenshot conventions and the checklist template come from TEST-102.
- Also measure where LOD switches happen (VERIFY #9): fly or slew away slowly from the lineup and note the distance of each visible switch. Compare with the design distances (150 m, 600 m, 2 km). Check whether Dev Mode has an LOD debug view.
- VERIFY #10: note whether placed objects support lean (pitch/bank) and scale. Use SPIKE-003's template notes and try it.
- If GEN's manifest-driven variant selection exists (see `plans/detailed/04-fs2024-integration.md`), also build the test neighborhood (T1) with it. If not, skip that step and say so.
- This task doesn't change models. It records findings.

## Steps

1. Build `palmfix-assets` (as in ASSET-014) and load it in Dev Mode.
2. Place short, medium and tall 15 m apart on flat ground outside photogrammetry. Record the coordinates in `assets/reviews/washingtonia_robusta.md`.
3. Take screenshots at 2 m, 150 m and 600 m, at noon and at golden hour (17:30-18:30 local in summer, or whatever puts the sun about 10° up). Save them as `tests/visual/lineup-washingtonia_robusta/<YYYY-MM-DD>/<view>_<time>.png`.
4. Slow fly-away: record the distances where LOD0 to 1, 1 to 2 and 2 to 3 switch, and how noticeable each pop is (none, slight, distracting).
5. Check the base contact on flat ground at 2 m: no gap, no visible sinking.
6. Compare with 3 reference photos from `assets/reference/washingtonia_robusta.md` at similar angles. Note trunk taper, crown size and frond color.
7. If available, build T1 with palmgen using the manifest and take the TEST-102 viewpoints.
8. Fill in the checklist in `assets/reviews/washingtonia_robusta.md` and list fixes as `P1` (must fix), `P2` (should fix) or `P3` (later), each with the screenshot it refers to.

## Acceptance criteria

- [ ] The review file has coordinates, a filled checklist, LOD switch distances and a fix list.
- [ ] 12 lineup screenshots (3 views x 2 times x 2 minimum) are saved under `tests/visual/lineup-washingtonia_robusta/`.
- [ ] VERIFY #9 and #10 findings are logged.

## Verification

```bash
ls tests/visual/lineup-washingtonia_robusta/*/ | wc -l     # >= 6
grep -n '^- \[' assets/reviews/washingtonia_robusta.md     # checklist lines present
```
Reviewer (human): open the screenshots and confirm the fix list matches what's visible.

## Log

- 2026-11-21 [plan-breakdown] Task created.
