---
id: ASSET-008
title: "Agree and set up the large-file policy (Git LFS or external store) for assets"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#large-file-policy"
depends_on: []
requires: [human]
agent: task-planner
estimate_h: 1.5
touches: [.gitattributes, assets/README.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-21
---

## Goal

The user has approved how `.blend` files, textures and binary exports are stored, and the repo enforces it (`.gitattributes` for Git LFS, or a documented external store) before the first binary asset is committed.

## Context

- The proposal is in `#large-file-policy`: Git LFS for `*.blend`, `*.png`, `*.bin` and `*.ktx2` under `assets/`, and `*.png` under `tests/visual/`. The fallback is an external store with path + SHA-256 recorded in `SOURCES.md`.
- This is a user decision (VERIFY). Don't set up LFS without the user's explicit OK.
- `.gitattributes` may already exist from ARCH-001 or INFRA. If it does, append a clearly marked block; don't rewrite other areas' lines.
- If LFS is chosen, check that the git host supports it and has enough quota for an expected 0.5-2 GB. Ask the user what plan or quota they have.

## Steps

1. Show the user the proposal and the fallback, with the expected size (roughly 20-100 MB per species once textures and blends are in), and ask them to pick one. Record the answer in this task's Log, quoting the user.
2. If LFS: run `git lfs install` (once per machine), then add patterns to `.gitattributes`, for example `assets/**/*.blend filter=lfs diff=lfs merge=lfs -text` (same for png, bin, ktx2, and `tests/visual/**/*.png`).
3. If external store: add a `.gitattributes` comment block saying binaries are not committed, and make sure `.gitignore` coverage is requested from the ARCH/INFRA owner (log the request; don't edit `.gitignore` here).
4. Create `assets/README.md`: a 10-20 line pointer file covering the folder layout (link to `plans/detailed/03-palm-assets.md#paths-and-folder-layout`), the storage policy chosen, and the commands `python -m palmcore.assets check|build-manifest|validate`.

## Acceptance criteria

- [ ] The user's choice is quoted in the Log.
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
