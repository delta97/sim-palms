---
id: RISK-002
title: Audit model, texture and tool licenses for palm assets
status: in_progress
phase: 2
area: RISK
kind: research
plan_ref: "plans/detailed/07-risks-and-open-questions.md#license-audit"
depends_on: []
requires: [network]
agent: scribe
estimate_h: 4
touches: [docs/licenses/models-and-tools.md]
owner: claude-agent
branch: task/risk-002-audit-model-texture-and-tool-licenses-fo
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/RISK-002"
updated: 2026-11-22
---

## Goal

One file records the terms that govern palm assets: candidate 3D model sources, texture sources, the MSFS SDK terms on distributing built packages, and the Blender exporter's license. DEC-002 (build or license) and DEC-008 (binary storage) decide from it, so it should be done before Phase 3 starts.

## Context

- Plan: `plans/03-palm-assets.md` section 5 ("Many stock model licenses forbid redistributing the model file, and a mod package does redistribute it").
- Risks: R-12, R-14, R-19.
- Five species: Washingtonia robusta, Washingtonia filifera, Phoenix canariensis, Syagrus romanzoffiana, Archontophoenix cunninghamiana.
- Do not state legal conclusions. Quote terms, list questions for the user.

## Steps

1. Model marketplaces: for 3-4 common marketplaces (for example TurboSquid, CGTrader, Sketchfab store, Fab), record their standard license name and quote the clauses on: use in games or mods, redistribution of the model inside a distributed product, extraction risk, storage in a public repository, modification.
2. For each of the 5 species, find up to 2 candidate models (URL, price, triangle count, formats, license type). Note which have LODs.
3. Texture sources: record terms of at least two free texture libraries (for example Poly Haven, ambientCG) and any bark/frond texture sources found.
4. Tools: MSFS 2024 SDK terms as they apply to distributing packages built with `fspackagetool`; license of the Blender exporter `io_scene_gltf2_msfs_2024` (check its repository or the SDK folder license file); Blender itself (GPL; note that output files are not covered, quoting Blender's own FAQ).
5. Write `docs/licenses/models-and-tools.md`: intro ("not legal advice; terms quoted as of the date checked"), sections Marketplaces, Candidate models (table per species), Textures, Tools, then "Questions for the user" (numbered). Include a column "Usable if published? (terms clear / unclear / restrictive)" phrased as a reading of the quoted terms, with questions where unclear.

## Acceptance criteria

- [ ] At least 3 marketplaces with quoted redistribution clauses and a date checked.
- [ ] Each of the 5 species has 0-2 candidate models recorded (0 is fine if none found; say so).
- [ ] SDK and exporter terms each have a URL or file path and a quote.
- [ ] A "Questions for the user" list exists; no legal conclusions are stated.

## Verification

```bash
test -f docs/licenses/models-and-tools.md && echo ok
for s in robusta filifera canariensis romanzoffiana cunninghamiana; do grep -qi "$s" docs/licenses/models-and-tools.md && echo "found $s" || echo "MISSING $s"; done
grep -n "io_scene_gltf2_msfs_2024" docs/licenses/models-and-tools.md
grep -n "Questions for the user" docs/licenses/models-and-tools.md
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/risk-002-audit-model-texture-and-tool-licenses-fo worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/RISK-002
