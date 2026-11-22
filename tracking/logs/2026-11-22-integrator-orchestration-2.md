# Session log: 2026-11-22, integrator, orchestration part 2 (LiDAR, local CI, FX Stage A, issue sync)

- **Started / ended:** 2026-11-22 (continues [part 1](2026-11-22-integrator-orchestration.md))
- **Agent / model / person:** integrator session orchestrating specialist subagents, one per task, each in its own worktree
- **Branch / worktree:** `main` (primary checkout); task branches in `../sim-palms-worktrees/<ID>`, all removed after merge
- **Tasks:** 18 more tasks todo -> done (SCAN-007, -020, -024, -025, -027, -028, TEST-008, -013, -014, FX-002, -003, -004, -005, -008, -009, -010, -011, -012), INFRA-001 review -> done, FX-014 todo -> blocked (code merged), FX-026 created

## Goal

Finish the agent-doable work after part 1: the Phase 4 LiDAR chain, remaining test tooling, and (on the user's go-ahead) Phase 7 Stage A; move CI off GitHub at the user's request; bring GitHub issues back in step with the task files.

## What changed

- **LiDAR wired end to end:** `palmscan run` runs EPT tiles -> CHM -> crowns -> rules -> inventory merge -> classifier -> QA and `palmscan eval` (SCAN-020..028). Real PDAL and 3DEP data untested.
- **Phase 7 Stage A (`palmfx.offline`):** scaffold, camera model, depth decoder + ReShade shader (shader untested), synthetic scene generator, ingest + pose interpolation, calibration, masks by projection and by heuristics, mask metrics, inpainting runner.
- **CI:** GitHub Actions `python` and `tracking` workflows disabled (user request). `scripts/ci.py` mirrors them locally and gates every merge (`--install` builds `.venv` with `dev,scan,lidar,gen,fx`).
- **Integration fixes made on `main`:** CHM timing ceiling relaxed under `CI` (SCAN-022); `fx` extra added to local CI (FX-002 needs opencv); FX-004 generator renamed its suffix key to `reshade_suffixes` to match ingest, with a cross-check test; FX-010 `mask-project` now reads `calib/intrinsics.json` and `calib/pose_bias.json` as written by FX-009, with a test.
- **FX-014 / FX-026:** FX-014's code merged, task `blocked`. FX-026 (#215) created for the LaMa weights download, checksum and end-to-end run; GitHub "blocked by" links: #215 -> #202 -> #203, #205, #206; #215 is a sub-issue of GATE-P7 (#9).
- **Issue sync:** `scripts/issues.py` (written in INFRA-001 on the bootstrap branch but never merged) cherry-picked without its workflow and run locally: label set created, 74 stale issue bodies regenerated from the task files, `area:*`/`requires:*`/`status:*` labels applied.
- **Docs:** root `README.md` status and quick start, `tests/README.md` local-CI rows and counts, `AGENTS.md` (ci.py, local issue sync), `tracking/README.md`, `STATUS.md`.

## Verification

- `python scripts/ci.py` on `main`: all steps PASS; 2,054 passed, 3 skipped; palmcore coverage 95.4%.
- `python scripts/tasks.py validate`: 214 tasks, 0 errors; `conflicts`: 0.
- `python scripts/issues.py sync --dry-run` after the sync: see the integrator's final check (expected 0 pending updates).
- `palmscan --help`, `palmscan run --help`, `palmfix --help` run from `.venv`.

## Decisions and findings

- The user approved running Phase 7 Stage A ahead of FX-001 (in chat, three times, batch by batch).
- Parallel tasks built against unconfirmed formats drift: two real mismatches were caught only by cross-checking after merge (FX-004/FX-008 suffix key, FX-009/FX-010 calibration file names). When two in-flight tasks share a file format, check the pair at merge time.
- `scripts/issues.py` matches issues by title, so the task files do not need `issue:` numbers; the bootstrap commit that added them (8ab97b3) was left unmerged on purpose.

## Open issues

- FX-026 needs the user's OK (downloading and loading pickled model weights) and a machine with torch.
- FX-009's click UI has never run on a display; its acceptance box stays open.
- Known data gaps (StreetsLA WFS, Microsoft footprint downloader, `palmgen` Overpass client) are listed in `STATUS.md`; no tasks yet.

## Handoff: next steps

1. User: DEC-004, then SPIKE-001 on the sim PC; review ADR-0001 and ADR-0013; FX-026 go-ahead.
2. After each push to `main`: `python scripts/ci.py` (before) and `python scripts/issues.py sync` (after).
3. When sim results land: FX-001/FX-006/FX-007 confirm the capture formats; update the VERIFY items in `palmfx/offline/` and plan 08.
