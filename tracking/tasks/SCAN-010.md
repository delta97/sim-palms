---
id: SCAN-010
title: "Species priors and deterministic prior sampling"
status: review
phase: 1
area: SCAN
kind: build
plan_ref: "plans/detailed/02-detection-pipeline.md#w8-species-priors"
depends_on: [SCAN-001]
requires: [none]
agent: geo-data-engineer
estimate_h: 2
touches: [palmscan/classify/priors.py, tests/unit/palmscan/test_scan_priors.py]
owner: claude-agent
branch: task/scan-010-species-priors-and-deterministic-prior-s
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-010"
updated: 2026-11-22
---

## Goal

Species priors are computed from a region's inventory (replacing the placeholder values in region YAMLs), and palms without a species get a deterministic, reproducible sample from those priors.

## Context

- Spec: plan_ref section W8.
- Determinism matters: the same palm must get the same prior species on every run, so sampling hashes the palm's stable key instead of using a RNG.
- `washingtonia_filifera` weight folds into `washingtonia_robusta` before sampling (plan Q2).

## Steps

1. Implement `compute_priors`, `merge_priors(computed, configured, min_n=30)`, `sample_species(priors, key)` and `priors_yaml(priors)` in `palmscan/classify/priors.py` as specified.
2. `sample_species`: `u = int(sha1(key).hexdigest()[:12], 16) / 16**12`; cumulative walk over alphabetically sorted keys; filifera fold first; empty priors -> `ValueError`.
3. Tests: shares from a known list (genus-level and unknown excluded); `min_n` switch between computed and configured; same key -> same species across calls; 10,000 synthetic keys reproduce the priors within 2 percentage points; filifera never returned; YAML output parses back to the same dict.

## Acceptance criteria

- [x] `sample_species` is a pure function of `(priors, key)`.
- [x] Empirical distribution over 10,000 keys within 2 points of the priors.
- [x] `priors_yaml` output loads with `yaml.safe_load` into `{"species_priors": {...}}`.
- [x] Tests pass.

## Verification

```bash
pytest tests/unit/palmscan/test_scan_priors.py -q
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/scan-010-species-priors-and-deterministic-prior-s worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-010
- 2026-11-22 [claude-agent] Implemented palmscan/classify/priors.py: compute_priors (returns SpeciesMix with n_palms), merge_priors, sample_species (sha1 u, filifera folded into robusta, ValueError on empty), priors_yaml. Spec: plan W8.
- 2026-11-22 [claude-agent] Tests: pytest tests/unit/palmscan/test_scan_priors.py -> 11 passed (shares, min_n switch, order independence, pure sampling, 10,000-key distribution within 0.02, filifera never returned, YAML round trip).
- 2026-11-22 [claude-agent] Discrepancy: brief said use palmcore.ids stable_unit_float; plan W8 and task Step 2 specify sha1(key)[:12]. Followed the plan (deterministic, not hash()). Callers pass purpose-tagged keys e.g. species|<stable_key>. Plan W8 updated to document SpeciesMix/n_palms, needed for min_n.
- 2026-11-22 [claude-agent] SCAN-002 (species keys) not used: prior keys validated by pattern ^[a-z]+(_[a-z]+)+$ only; palm_unknown excluded explicitly. Full suite 873 passed, 1 skipped; ruff check, ruff format --check, mypy clean.
- 2026-11-22 [claude-agent] Status in_progress -> review.
