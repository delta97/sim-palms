---
id: REGION-012
title: "San Diego coastal: palmscan run, priors and QA review"
status: todo
phase: 6
area: REGION
kind: test
plan_ref: "plans/detailed/05-phases.md#per-region-task-pattern"
depends_on: [REGION-011]
requires: [network, human]
agent: geo-data-engineer
estimate_h: 2
touches: [regions/san-diego-coastal.yaml, tracking/logs/REGION-012-qa.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

A validated, LiDAR-enriched `palms.geojson` for the whole San Diego coastal region, with region-specific species priors and a QA review that finds no blocking problems.

## Context

- Pattern and order: `plans/detailed/05-phases.md#per-region-task-pattern`. Commands: `docs/regions/RUNBOOK.md` (REGION-001).
- Region: **San Diego coastal**, file `regions/san-diego-coastal.yaml`, `id_prefix: sdc` (ARCH-008 wrote the starting file).
- If this region was the Phase 1-5 test region (it contains the DEC-004 block), most of this step was done before: review and update instead of starting over, and say so in the Log.
- If DEC-011 (ADR-0012) drops or reorders this region, set this task to `dropped` or adjust `depends_on`, and log why.
- Data goes to `data/<region>/` and is never committed. Only the YAML and the QA log are committed.
- Phase 1 and 4 targets apply loosely at region scale: spot-check, don't hand-label (R-04 stale data, R-05 capture-date mismatch).

## Steps

1. `palmscan run --region san-diego-coastal` (network; LiDAR tiles can take a while). Then `palmscan run --region san-diego-coastal --offline` and confirm `palms.geojson` is byte-identical.
2. Contract check: `python -m tests.helpers.contract data/san-diego-coastal/palms.geojson --region regions/san-diego-coastal.yaml` exits 0.
3. `palmscan priors --region san-diego-coastal`; put the printed priors into `species_priors` in the YAML; rerun step 1 offline.
4. Read `qa_summary.md`: palm counts by source and species, share LiDAR-only, `data_vintage` per source, reject reasons. Copy the key numbers into `tracking/logs/REGION-012-qa.md`.
5. Open `qa_map.gpkg` over aerial imagery. Look at three streets and one park or beach chosen at random. Note obvious misses and false positives, and any area where the inventory looks stale.
6. Write a verdict line: ok, ok with notes, or blocked (with the reason and the task needed).

## Acceptance criteria

- [ ] `--offline` rerun is byte-identical.
- [ ] Contract check exits 0.
- [ ] `species_priors` come from `palmscan priors` for this region.
- [ ] `tracking/logs/REGION-012-qa.md` has counts, vintages, the spot review notes and a verdict.

## Verification

```bash
python -m tests.helpers.contract data/san-diego-coastal/palms.geojson --region regions/san-diego-coastal.yaml
grep -iE "verdict" tracking/logs/REGION-012-qa.md
```

## Log

- 2026-11-22 [plan-breakdown] Task created.
