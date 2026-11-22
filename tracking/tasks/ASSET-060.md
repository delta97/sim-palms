---
id: ASSET-060
title: "Florida species: reference sheets for cabbage, royal, coconut and foxtail palm"
status: todo
phase: 6
area: ASSET
kind: research
plan_ref: "plans/detailed/03-palm-assets.md#w13-florida-set"
depends_on: [ASSET-100]
requires: [network]
agent: asset-pipeline-artist
estimate_h: 4
touches: [assets/reference/sabal_palmetto.md, assets/reference/roystonea_regia.md, assets/reference/cocos_nucifera.md, assets/reference/wodyetia_bifurcata.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

Reference sheets for the 4 Florida species, in the same format as the SoCal sheets (ASSET-001), so low-detail models can be built.

## Context

- Format: copy the section structure of `assets/reference/washingtonia_robusta.md` (Identification, Photos, Proportions, Look-alikes, Color notes, Sources).
- Species keys: `sabal_palmetto`, `roystonea_regia`, `cocos_nucifera`, `wodyetia_bifurcata`. VERIFY that they match the `species` values in the palms.geojson schema (ARCH-002). If not, log it and use the schema's keys.
- Florida is low detail (`#w13-florida-set`): 2 variants per species. Propose 2 target heights per species from the sources, in each sheet's `## Notes for W5`.
- Links only, no committed photos.

## Steps

1. Write one sheet per species with all six sections, 6-10 photo links with license notes, a proportions table with ranges and sources, and look-alikes (royal vs foxtail; coconut vs queen).
2. Add `## Notes for W5` with 2 proposed variant heights and crown diameters per species.
3. Check the species keys against the ARCH-002 schema and log the result.

## Acceptance criteria

- [ ] 4 sheets exist with all sections, and each has 6 or more photo links.
- [ ] Each sheet proposes 2 variant heights.
- [ ] The species-key check is logged.

## Verification

```bash
ls assets/reference/{sabal_palmetto,roystonea_regia,cocos_nucifera,wodyetia_bifurcata}.md
for f in assets/reference/{sabal_palmetto,roystonea_regia,cocos_nucifera,wodyetia_bifurcata}.md; do grep -c '^## ' "$f"; done   # >= 7 each
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
