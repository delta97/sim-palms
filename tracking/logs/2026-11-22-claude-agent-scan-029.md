# Session log: 2026-11-22, claude-agent, scan-029 accuracy in-run QA

- **Started / ended:** 2026-11-22 (local)
- **Agent / model / person:** claude-agent / Claude Haiku 5.5
- **Branch / worktree:** task/scan-029-run-the-test-010-accuracy-evaluation-fro / C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/SCAN-029
- **Tasks:** SCAN-029 (in_progress -> review)

## Goal

Run the TEST-010 accuracy evaluation from palmscan's QA: load a labelled site through the TEST-009
loaders, evaluate it with TEST-010 (no metric code in palmscan), add the SCAN-only fallback height
error, and write `accuracy.json` and the Accuracy section Markdown for SCAN-012's `QaContext.accuracy_md`.

## What changed

- `palmscan/qa/accuracy.py`: `load_evaluator`, `evaluate_site`, `fallback_height_error`,
  `accuracy_doc`, `write_accuracy`, `accuracy_section_md` (commit f2934ca).
- `tests/unit/palmscan/test_scan_accuracy.py`: 10 tests (commit f2934ca).
- `tests/fixtures/palmscan/accuracy/`: synthetic `pred.geojson`, `pred_empty.geojson`, site folder
  `T9/` (TEST-009 format), `README.md` (commit f2934ca).
- `tracking/tasks/SCAN-029.md`: acceptance boxes ticked, log entries.

## Verification

- `pytest tests/unit/palmscan/test_scan_accuracy.py -q`: 10 passed.
- `pytest -q`: 1587 passed, 1 skipped (existing skip: no local palmscan output).
- `ruff check .`: clean. `ruff format --check .`: clean. `mypy`: no issues in 66 files.

## Decisions and findings

- Site id `T9`, not `site_TX`: TEST-009 site ids must match `T[0-9]+`.
- `evaluate_site` returns `{profile: {"result", "failures", "not_checked"}}`; `result` is the
  TEST-010 `evaluate` output unchanged. Missing evaluator: warning appended and `{}` returned.
  Missing or invalid site folder raises the TEST-009 `GroundTruthError`.
- `fallback_height_error` uses `MergeParams().region_median_min_n` (5) and counts palms with a
  non-null species. Plan wording says "species-level names"; that filter is not applied here.
  VERIFY against SCAN-013 once the pipeline wires it.
- The fixture's `combined` profile fails on purpose (precision 0.80, recall 0.80), so the
  failure path is exercised.
- Not done here: wiring into `pipeline.py` / `cli.py` (`--eval-site`, `eval` subcommand). Those
  belong to SCAN-013 and SCAN-028, which are not merged yet.

## Open issues

- The `--eval-site` flag and `accuracy.json` write from the run are not wired (see above).

## Handoff: next steps

1. After SCAN-013 is merged, call `evaluate_site(palms_fc, site, repo_root=...)` from the run,
   collect its `warnings` into `QaContext.warnings`, pass `accuracy_section_md(accuracy_doc(...))`
   as `QaContext.accuracy_md`, and `write_accuracy` into the run folder.
2. Reviewer: check the species filter in `fallback_height_error` against the plan's "species-level" wording.
