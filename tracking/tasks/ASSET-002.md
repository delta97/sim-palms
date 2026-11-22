---
id: ASSET-002
title: "Collect build-vs-license inputs for DEC-002 (palm models)"
status: todo
phase: 3
area: ASSET
kind: research
plan_ref: "plans/detailed/03-palm-assets.md#w1-reference-and-build-vs-license"
depends_on: []
requires: [network]
agent: asset-pipeline-artist
estimate_h: 3
touches: [assets/reference/build-vs-license.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

A fact sheet that lets the user decide DEC-002 (build or license the palm models) in one sitting: candidate model sources, their license terms for redistribution inside a mod, cost, quality, and how much pipeline work remains.

## Context

- The decision belongs to DEC-002 (plan 07). This task only collects facts. Don't recommend buying anything.
- Key constraint (source plan section 5): a Community package redistributes the model file. Many stock licenses forbid that. If the user publishes (DEC-001), this matters a lot. For personal use it may still matter, depending on the license.
- Whatever the source, the model still needs our LODs, MSFS materials and the conventions in `#w4-blender-scene-conventions`.
- Don't paraphrase license terms from memory. Quote the clause and link the license page.

## Steps

1. List 4-8 candidate sources (stock 3D marketplaces, tree-generator products, free CC0 model sites). For each, find palm models covering any of the 5 SoCal species.
2. For each candidate, fill a table row: source, product/model link, species covered, price, license name, a quoted redistribution clause (and link), 'mod redistribution allowed?' (yes/no/unclear), formats, triangle count if stated, texture resolution, LODs included.
3. Estimate the remaining work per licensed model: LOD1-3, material conversion, origin and scale fixes, export. Use the task index estimates in the plan_ref as the 'build' baseline.
4. Write three option summaries (build, license, hybrid) with hours, cost and license risk. List open questions for the user, including how DEC-001 (personal vs publish) changes the answer.
5. Save as `assets/reference/build-vs-license.md` and log the file path in DEC-002's Log with `python3 scripts/tasks.py log DEC-002 "Inputs ready: assets/reference/build-vs-license.md" --by <you>`.

## Acceptance criteria

- [ ] At least 4 candidates with a quoted, linked license clause each.
- [ ] Each candidate is marked yes, no or unclear for mod redistribution.
- [ ] Build, license and hybrid are summarized with hours and cost.
- [ ] DEC-002's Log points to the file.

## Verification

```bash
test -f assets/reference/build-vs-license.md
grep -ciE 'redistribut' assets/reference/build-vs-license.md   # expect >= 4
python3 scripts/tasks.py show DEC-002 | grep build-vs-license
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
