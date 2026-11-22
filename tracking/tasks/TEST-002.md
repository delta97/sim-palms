---
id: TEST-002
title: Add the golden-file comparison helper with an update flag
status: in_progress
phase: 2
area: TEST
kind: build
plan_ref: "plans/detailed/06-testing.md#golden-files"
depends_on: [TEST-001]
requires: [none]
agent: test-engineer
estimate_h: 3
touches: [tests/helpers/golden.py, tests/conftest.py, tests/unit/helpers/test_golden.py]
owner: claude-agent
branch: task/test-002-add-the-golden-file-comparison-helper-wi
worktree: "C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-002"
updated: 2026-11-22
---

## Goal

`tests/helpers/golden.py` gives GEN (and anyone else) exact-match golden tests for generated XML, with `pytest --update-golden` to accept new output on purpose.

## Context

- Spec: `plans/detailed/06-testing.md#golden-files` and the golden part of `#helper-api`.
- GEN owns the golden cases under `tests/golden/<case>/`; this task owns only the helper. Don't create real cases here; self-tests use `tmp_path` as the root.
- TEST-001 created `tests/conftest.py`; this task adds the `--update-golden` option and the `golden` fixture to it.

## Steps

1. `tests/helpers/golden.py`:
   - `GOLDEN_ROOT = REPO_ROOT / "tests" / "golden"`.
   - `normalize_newlines(text)`: CRLF and CR to LF; exactly one trailing LF.
   - `class GoldenMismatch(AssertionError)` and `class GoldenUpdated(UserWarning)`.
   - `_update_requested(explicit)`: explicit arg > module flag set from the pytest option > env `PALMFIX_UPDATE_GOLDEN=1`. If true and env `CI` is set, raise `RuntimeError("refusing to update golden files in CI")`.
   - `assert_golden(actual, case, relpath, *, update=None, normalize=normalize_newlines, root=GOLDEN_ROOT)`: str input is normalized and compared as UTF-8; bytes compared raw when `normalize=None`. Missing file without update: fail with the hint text from the plan. Mismatch: `GoldenMismatch` with the path and a `difflib.unified_diff` capped at 200 lines (say how many lines were cut). Update: create parent dirs, write, `warnings.warn(GoldenUpdated(...))`.
   - `assert_golden_dir(actual_dir, case, *, pattern="**/*", update=None, normalize=normalize_newlines, root=GOLDEN_ROOT)`: compare file sets (missing, extra) and contents; collect all problems into one failure. In update mode, write all actual files and delete extra golden files under that case.
2. `tests/conftest.py`: add `--update-golden` (store_true) in `pytest_addoption`; in `pytest_configure` set the module flag in `tests.helpers.golden`; add fixture `golden` returning an object with `.check(actual, case, relpath, normalize=...)` and `.check_dir(actual_dir, case, pattern=...)` bound to `GOLDEN_ROOT`.
3. `tests/unit/helpers/test_golden.py` (all with `root=tmp_path`): match passes; one changed byte fails and the diff shows the line; CRLF actual vs LF golden passes; missing file fails with the hint; `update=True` writes and warns; `update=True` with `monkeypatch.setenv("CI", "1")` raises; dir mode reports a missing and an extra file in one message; update in dir mode removes the extra file.
4. Add a short module docstring with a usage example for GEN.

## Acceptance criteria

- [ ] All self-tests pass.
- [ ] `pytest --update-golden` is accepted by the CLI (`pytest --help | grep update-golden`).
- [ ] Failure output names the golden path and shows a unified diff of at most 200 lines.
- [ ] Update refused when `CI` is set.

## Verification

```bash
pytest tests/unit/helpers/test_golden.py -q
pytest --help | grep -- --update-golden
CI=1 PALMFIX_UPDATE_GOLDEN=1 pytest tests/unit/helpers/test_golden.py -q   # suite still passes; the refusal path is itself tested
python3 scripts/tasks.py validate
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [claude-agent] Claimed. branch=task/test-002-add-the-golden-file-comparison-helper-wi worktree=C:/Users/colep/OneDrive/Desktop/sim-palms-worktrees/TEST-002
