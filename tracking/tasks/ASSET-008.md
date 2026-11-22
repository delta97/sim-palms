---
id: ASSET-008
title: "Implement the asset large-file policy decided in DEC-008 (.gitattributes, assets/README.md)"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#large-file-policy"
depends_on: [DEC-008]
requires: [none]
agent: task-planner
estimate_h: 1.5
touches: [.gitattributes, assets/README.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

The storage policy decided in DEC-008 (ADR-0009) is enforced in the repo (`.gitattributes` for Git LFS, or a documented external store) before the first binary asset is committed. The decision itself is DEC-008's; this task only implements it.

## Context

- The proposal is in `#large-file-policy`: Git LFS for `*.blend`, `*.png`, `*.bin` and `*.ktx2` under `assets/`, and `*.png` under `tests/visual/`. The fallback is an external store with path + SHA-256 recorded in `SOURCES.md`.
- The decision (LFS or external, and whether `tests/visual/**` screenshots are JPEG in plain git or LFS) is ADR-0009 from DEC-008. Don't set up LFS unless ADR-0009 says so.
- `.gitattributes` may already exist from ARCH-001 or INFRA. If it does, append a clearly marked block; don't rewrite other areas' lines.
- If LFS is chosen, check that the git host supports it and has enough quota for an expected 0.5-2 GB. Ask the user what plan or quota they have.

## Steps

1. Read ADR-0009 (DEC-008). Record the chosen policy and the screenshot rule in this task's Log with the ADR link.
2. If LFS: run `git lfs install` (once per machine), then add patterns to `.gitattributes`, for example `assets/**/*.blend filter=lfs diff=lfs merge=lfs -text` (same for png, bin, ktx2, and `tests/visual/**` images only if ADR-0009 chose LFS for screenshots).
3. If external store: add a `.gitattributes` comment block saying binaries are not committed, and make sure `.gitignore` coverage is requested from the ARCH/INFRA owner (log the request; don't edit `.gitignore` here).
4. Create `assets/README.md`: a 10-20 line pointer file covering the folder layout (link to `plans/detailed/03-palm-assets.md#paths-and-folder-layout`), the storage policy chosen, and the commands `python -m palmcore.assets check|build-manifest|validate`.

## Acceptance criteria

- [ ] The Log links ADR-0009 and states the policy applied.
- [ ] `.gitattributes` reflects the choice. With LFS, `git check-attr filter assets/blender/x/x.blend` prints `lfs`.
- [ ] `assets/README.md` states the policy.

## Verification

```bash
git check-attr filter -- assets/blender/test/test.blend assets/blender/test/textures/tx_test_bark_albedo.png
# LFS chosen: both print 'filter: lfs'
grep -n -i 'lfs\|external' assets/README.md
```

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [reconcile] Now the implementation of DEC-008 (ADR-0009) and depends on it: the user's decision (including the screenshot JPEG-vs-LFS rule folded in from TEST) is made in DEC-008; this task applies it. requires changed human -> none. Cross-area reconciliation.
