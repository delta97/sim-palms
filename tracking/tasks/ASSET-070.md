---
id: ASSET-070
title: "Spike: wrap one palm variant as a SimObject and spawn it via SimConnect"
status: todo
phase: 5
area: ASSET
kind: spike
plan_ref: "plans/detailed/03-palm-assets.md#w12-simobject-wrappers"
depends_on: [ASSET-014, SPIKE-005]
requires: [windows-sim]
agent: msfs-sdk-specialist
estimate_h: 4
touches: [assets/simobjects/templates/, assets/simobjects/README.md, tests/fixtures/palmcore/assets/simobject_sample/]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

One robusta variant spawns as a SimObject by title, using SPIKE-005's SimConnect script. The working container files are captured as templates, and the SimObject VERIFY items are answered, so ASSET-071 can generate wrappers for every variant.

## Context

- Only needed if the Phase 5 bake-off tests live spawning (`#w12-simobject-wrappers`). Plan 04 section 6 says spawning uses `SimConnect_AICreateSimulatedObject_EX1` with the container title.
- SPIKE-005 has a C# script that spawns a default static SimObject. Reuse it with our title.
- VERIFY #11: the 2024 SimObject container format for a static object; whether it can reference the model-library model or needs its own model copy; whether a spawned object can be scaled; whether titles must be unique across packages. Find these in the SDK docs and SDK samples. Don't guess. Quote doc pages or sample paths.
- Title convention: `PalmFix Washingtonia robusta Medium` (`#naming-conventions`).
- Wrappers live in a separate package, `palmfix-assets-simobjects`, under `assets/simobjects/`. Build the spike package under `build/` only.

## Steps

1. Find the SDK docs and sample for a static/scenery SimObject container in 2024. Note the paths in `assets/simobjects/README.md`.
2. Build a throwaway package in `build/simobject-spike/` containing one SimObject container for `palmfix_washingtonia_robusta_medium`. First try referencing the model-library model; if that doesn't work, copy the model files in.
3. Build with fspackagetool and start the sim with the package active.
4. Run SPIKE-005's script with the title `PalmFix Washingtonia robusta Medium` at a known flat coordinate. Confirm the palm appears and sits on the ground.
5. Try scaling at spawn, if the API or container supports it. Record the result.
6. Copy the working container files into `assets/simobjects/templates/` with placeholders `{{TITLE}}`, `{{MODEL_NAME}}`, `{{MODEL_GUID}}` (and whatever else varies). Copy one concrete instance into `tests/fixtures/palmcore/assets/simobject_sample/`.
7. Write the VERIFY #11 answers and the chosen package layout in `assets/simobjects/README.md`.

## Acceptance criteria

- [ ] A spawned palm is visible in the sim by title. Screenshot path in the Log.
- [ ] Templates and a sample instance are committed.
- [ ] The README answers all four VERIFY #11 questions, each with a source or test result.

## Verification

On the sim PC: build the spike package, start the sim, run the SPIKE-005 script with the title, and confirm the palm appears at the coordinate (screenshot).
```bash
ls assets/simobjects/templates/ tests/fixtures/palmcore/assets/simobject_sample/
grep -n -i 'scale\|unique\|model' assets/simobjects/README.md
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
