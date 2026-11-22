# Session log: 2026-11-22, claude-agent, asset-002

- **Started / ended:** 2026-11-22
- **Agent / model / person:** claude-agent
- **Branch / worktree:** task/asset-002-collect-build-vs-license-inputs-for-dec, C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/ASSET-002
- **Tasks:** ASSET-002 (in_progress -> review)

## Goal

Fact sheet for DEC-002 (build or license the palm models), building on the RISK-002 audit.

## What changed

- `assets/reference/build-vs-license.md`: 8 sources with quoted clauses and yes/no/unclear, per-species quality against `assets/budgets.yaml`, build-hour baseline from the plan 03 task index, remaining-work estimates, build/license/hybrid table, open questions, VERIFY list.
- `tracking/tasks/DEC-002.md`: Log line pointing to the file (required by ASSET-002 step 5).

## Verification

- `test -f` ok; `grep -ciE redistribut` = 7 (>= 4); `tasks.py show DEC-002 | grep build-vs-license` matches; `tasks.py validate` run before commit.

## Decisions and findings

- Only CC BY (PlantCatalog) and CC0 sources read as clear for redistribution; all CC BY palms are 8x-65x over LOD0 max and the smallest are infants.
- No CC BY Archontophoenix cunninghamiana (only A. alexandrae); queen palm candidate is 3,888 faces, quality unverified.
- Licensing can only affect the 32 LOD0 hours of the 90 species hours in the plan; hour estimates for conversion are mine, not measured.
- Paid marketplace prices stay VERIFY (CGTrader/TurboSquid pages returned empty or 403). No ADR written (DEC-002 owns ADR-0003).

## Open issues

- VERIFY items listed in the file (PlantCatalog formats/textures need a Sketchfab login).

## Handoff: next steps

1. DEC-002: ask the user the questions in section 6 of the file.
