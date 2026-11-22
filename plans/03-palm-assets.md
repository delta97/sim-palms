# 03. Palm Asset Library (`palm-assets`)

## Summary

The library is a set of 3D palm models, one per species, with 2–3 height variants each and several levels of detail (LODs). It's built in Blender and exported with the official MSFS 2024 plugin. It's the most labor-heavy part of the project, and the most important for how the result looks.

---

## 1. Species list

**SoCal set (Phase 3):**

| Key | Species | What to model | Typical size |
|---|---|---|---|
| `washingtonia_robusta` | Mexican fan palm | Very tall, thin trunk, small fan head, optional dead-frond skirt | 18–30 m tall, crown 3–5 m |
| `washingtonia_filifera` | California fan palm | Thick trunk, heavy dead-frond skirt | 12–18 m, crown 4–6 m |
| `phoenix_canariensis` | Canary Island date palm | Thick trunk with diamond leaf-base pattern, large round feathery crown | 12–20 m, crown 8–12 m |
| `syagrus_romanzoffiana` | Queen palm | Slim smooth trunk, drooping feathery fronds | 8–15 m, crown 5–7 m |
| `archontophoenix_cunninghamiana` | King palm | Smooth ringed trunk, green crownshaft, arching fronds | 10–15 m, crown 4–6 m |

**Florida set (later):** cabbage palm (*Sabal palmetto*), royal palm (*Roystonea regia*), coconut palm (*Cocos nucifera*), foxtail palm (*Wodyetia bifurcata*).

Size ranges are starting values for modeling. Real per-palm heights come from `palms.geojson`.

---

## 2. Per-model spec

**Variants per species:**
- 2–3 height variants (for example short, medium, tall), because scaling one model by ±40% distorts trunk thickness and frond size.
- At placement, pick the closest variant, then scale by up to ±15% to hit the exact height.
- Random yaw per palm. Optional slight lean (0–5°) for fan palms, which often lean in real life.
- One alternate crown per species if time allows, so rows of palms don't look copy-pasted.

**LOD targets (starting values to tune in performance testing):**

| LOD | Used at | Triangle budget | Notes |
|---|---|---|---|
| LOD0 | Street level to about 150 m | 3,000–6,000 | Full fronds, trunk detail |
| LOD1 | About 150–600 m | 800–1,500 | Simplified fronds |
| LOD2 | About 600 m–2 km | 150–300 | Frond cards |
| LOD3 | Beyond 2 km | Under 50 | Crossed quads or similar; just a silhouette |

The SDK's Blender exporter has an Auto LODs feature. Try it first, then hand-fix the LODs that look wrong.

**Materials:**
- Fronds: alpha-tested (cutout) material with a double-sided setting. Avoid alpha blending, which costs more and sorts badly.
- Trunk: tiling bark texture per species, plus a normal map at LOD0.
- Textures go in as PNG. MSFS 2024 uses KTX2 textures, and the package build converts them.
- Palms are evergreen, so no seasonal variants are needed. A dry-frond tint variant is optional.

---

## 3. Toolchain

1. **Blender** (use the version the SDK's plugin supports; check the SDK docs for your SDK version).
2. **SDK plugin `io_scene_gltf2_msfs_2024`**, found under `[SDK ROOT]\Tools\Blender\addons\`. Don't enable the 2020 plugin at the same time.
3. Export creates the `.gltf`, `.bin` and `.xml` files the package needs.
4. Assets go in `assets/PackageSources/` and are built as a **model library** asset group in the package project.

---

## 4. Two packagings

How palms get placed is decided in Phase 5, so the library has to support both:

| Packaging | Used by | What's needed |
|---|---|---|
| **Model library (scenery objects)** | Static placement inside the region package | Each model has a GUID; `palmgen` references the GUID in the scenery XML |
| **SimObjects** | Live spawning through SimConnect | Each variant wrapped as a SimObject with a container title (for example `PalmFix Washingtonia robusta Tall`); `palmlive` spawns by title |

Build the model library first. Add the SimObject wrappers only if the live option is being tested.

---

## 5. Build vs license

| Option | Pros | Cons |
|---|---|---|
| Build in Blender | Full control, free to redistribute | 20–40 hours for five species with variants and LODs |
| License 3D palm models | Fast, often high quality | Must allow use inside a redistributed mod; still needs LODs and MSFS materials |
| Hybrid | Licensed high-detail LOD0, hand-made lower LODs | License terms still apply |

If you plan to publish the mod, read the license before buying anything. Many stock model licenses forbid redistributing the model file, and a mod package does redistribute it.

---

## 6. Acceptance checks (per species)

- Looks right at street level, from 150 m and from 600 m, at noon and at golden hour.
- Base sits on the ground with no visible floating or sinking on flat terrain.
- LOD transitions don't pop noticeably at normal object LOD settings.
- Matches real reference photos for trunk shape, crown shape and frond color.
- Stays within the LOD budget above.

---

## Recap

- Five SoCal species, 2–3 height variants each, four LODs.
- Built in Blender with the SDK's 2024 exporter.
- Packaged as a model library first, with SimObject wrappers only if live spawning is tested.
- Check license terms before using any bought model in a published mod.
