---
id: RISK-009
title: Write attribution and credits text for published packages
status: todo
phase: 6
area: RISK
kind: doc
plan_ref: "plans/detailed/07-risks-and-open-questions.md#attribution-if-published"
depends_on: [DEC-010]
requires: [none]
agent: scribe
estimate_h: 2
touches: [docs/licenses/ATTRIBUTION.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

If the project is published, one file holds the credits and attribution text for every data source, model, texture and tool that ships, ready to paste into package docs and the flightsim.to page. Dropped if DEC-001 chose personal.

## Context

- Inputs: `docs/licenses/data-sources.md` and `docs/licenses/models-and-tools.md` (attribution clauses as quoted), ADR-0011 (what ships per region), ADR-0003 (model route), ADR-0010 (footprint source).
- OSM attribution guidance from the OSMF is quoted in the data-sources doc; follow the wording it asks for.
- This writes text only. Embedding it into packages is GEN work; name it as a follow-up if needed.

## Steps

1. List every item that ships per ADR-0011 and ADR-0003.
2. For each, copy the required attribution wording from the license doc (exact where the terms give wording).
3. Write `docs/licenses/ATTRIBUTION.md` with sections: Data sources, 3D models and textures, Tools, plus a short "Paste block" (plain text, under 1,500 characters) for the flightsim.to description.
4. If any item has no attribution wording in the audit, list it under "Missing wording; ask the user".
5. If a package-embedding step is needed, create a GEN task with `python3 scripts/tasks.py new GEN --title "Embed ATTRIBUTION text in region packages" --phase 6`.

## Acceptance criteria

- [ ] Every shipped item in ADR-0011 and ADR-0003 has a credit line.
- [ ] OSM attribution is present if any OSM-derived data ships.
- [ ] The paste block is under 1,500 characters.
- [ ] Missing wording is listed, not invented.

## Verification

```bash
test -f docs/licenses/ATTRIBUTION.md && echo ok
grep -n "OpenStreetMap" docs/licenses/ATTRIBUTION.md
python3 - <<'PY'
import re
t = open("docs/licenses/ATTRIBUTION.md").read()
m = re.search(r"## Paste block\n(.*?)(\n## |\Z)", t, re.S)
assert m, "no paste block"
print(len(m.group(1)), "chars (must be < 1500)")
PY
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
