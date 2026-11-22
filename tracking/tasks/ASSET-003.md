---
id: ASSET-003
title: "Install and pin Blender and the MSFS 2024 glTF exporter plugin"
status: todo
phase: 3
area: ASSET
kind: build
plan_ref: "plans/detailed/03-palm-assets.md#w2-toolchain-and-pipeline-smoke-test"
depends_on: [SPIKE-004, SPIKE-001]
requires: [blender, windows-sim]
agent: asset-pipeline-artist
estimate_h: 2
touches: [assets/TOOLCHAIN.md]
owner: ""
branch: ""
worktree: ""
updated: 2026-11-22
---

## Goal

A working Blender install on the sim PC with the SDK's MSFS 2024 exporter enabled, and `assets/TOOLCHAIN.md` recording the exact versions, so every later export is reproducible.

## Context

- Source plan section 3: use the Blender version the SDK's plugin supports. The plugin is `io_scene_gltf2_msfs_2024`, located under `[SDK ROOT]\Tools\Blender\addons\`. Don't enable the 2020 plugin at the same time.
- VERIFY: which Blender version is supported. Find it in the SDK docs for the installed SDK version (Blender plugin page linked in `plans/README.md` Sources) or in the plugin's own metadata (`bl_info` in its `__init__.py`). Don't guess.
- SPIKE-004 means the SDK is installed and `fspackagetool` works on this PC.

## Steps

1. Record the installed sim version and SDK version (from the SDK install folder or Dev Mode about screen).
2. Find the plugin folder under `[SDK ROOT]\Tools\Blender\addons\`. Read its `bl_info` (name, version, required Blender version) and the SDK docs page. Write both into TOOLCHAIN.md with the source.
3. Install exactly that Blender version (a portable zip is fine). Don't upgrade it later without re-running ASSET-004.
4. Install the plugin as the SDK docs describe. Enable it, and confirm in Preferences > Add-ons that no MSFS 2020 exporter is enabled.
5. Confirm that the plugin's export entry or panel appears in Blender. Take a screenshot of the add-on preferences entry for the Log.
6. Write `assets/TOOLCHAIN.md` with: `## Versions` (sim, SDK, Blender, plugin, date), `## Install steps` (numbered, reproducible on a clean PC), `## Known issues` (empty if none). Leave a `## Export settings` heading with 'TBD in ASSET-004'.

## Acceptance criteria

- [ ] TOOLCHAIN.md lists sim, SDK, Blender and plugin versions, each with where it was read from.
- [ ] The supported Blender version comes from the SDK docs or plugin metadata, not from memory.
- [ ] The plugin is enabled, and no 2020 exporter is enabled.

## Verification

Manual, on the sim PC:
1. Open Blender, go to Edit > Preferences > Add-ons and search 'MSFS'. Exactly one MSFS exporter (the 2024 one) should be enabled.
2. Go to File > Export. The plugin's export entry or panel is present.
3. `grep -n '^## ' assets/TOOLCHAIN.md` shows Versions, Install steps, Known issues and Export settings.

## Log

- 2026-11-21 [plan-breakdown] Task created.
- 2026-11-22 [integrator] Added SPIKE-001: the SDK install happens there; SPIKE-004 alone did not cover it.
