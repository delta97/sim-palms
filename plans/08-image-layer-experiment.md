# 08. Image-Layer Experiment (`palmfx`, optional)

## Summary

This is the fully live approach: change the rendered frame, the way DLSS 5 and ReShade do, instead of changing the scenery. It's the only way to fix blobs truly on the fly. It's also the hardest part, because something has to invent what's behind each blob, 60+ times a second, without flicker.

So it gets tested offline on screenshots first. The real-time version only gets built if the offline results look convincing.

---

## How it would work

Every frame:
1. **Find blob pixels.** Either detect them in the image (tall, narrow, sharp depth jumps with green-brown color), or project known palm locations from `palms.geojson` onto the screen using the camera position.
2. **Erase.** Fill those pixels with a believable guess at what's behind them (road, sky, buildings), using an inpainting model.
3. **Draw.** Render a palm at that spot, depth-tested so it sits correctly in front of and behind other things.

**Why DLSS 5 alone won't do it:** DLSS 5 treats the engine's frame and geometry as a fixed foundation and improves lighting and materials. It's designed not to replace objects, so a blob stays a blob.

---

## Stage A. Offline test (10–20 hours)

**Goal:** find out whether the erase step can look believable at all.

**Steps:**
1. **Capture:** at the Phase 0 test block, take 30–60 consecutive frames on a slow pass, with depth. ReShade can expose the depth buffer to effects and add-ons.
2. **Camera pose:** record aircraft or camera position and orientation through SimConnect alongside the frames. Verify which camera variables 2024 exposes; this is an open question.
3. **Masks:** make blob masks two ways and compare:
   - Project palm points from `palms.geojson` into each frame.
   - Detect from depth and color.
4. **Inpaint:** run an open-source inpainting model (for example LaMa) on the masked frames.
5. **Draw:** composite a rendered palm sprite at each location, scaled from depth.
6. **Judge:** single-frame quality, and flicker across consecutive frames.

**Go / no-go:**
- Single frames look believable at normal viewing distance, and
- Consecutive frames don't visibly shimmer, or a simple fix (reusing the previous frame's fill, blending over time) removes the shimmer.

If either fails, stop here. The scenery-based fix stays the answer.

---

## Stage B. Real-time version (only if Stage A passes)

**Shape:**
- A C++ ReShade add-on, reading color and depth.
- Inference on the GPU (TensorRT, or ONNX Runtime with DirectML), only on small tiles around masked areas, never the full frame.
- Camera pose from a small SimConnect helper, sent to the add-on each frame.
- Budget: a few milliseconds per frame on your GPU. Measure, don't assume.

**Known blockers to check first:**
- **Depth access:** ReShade turns off depth access when it detects multiplayer, to prevent cheating. Check whether MSFS 2024's online services trigger that.
- **Interaction with DLSS, frame generation and DLSS 5:** generated frames may not pass through the add-on the same way.
- **GPU cost:** DLSS 5 already costs performance. Stacking inpainting on top may not fit.
- **Temporal stability:** the hardest research problem in the whole project.

---

## Recap

- This is the only truly live fix, and also the riskiest.
- Test it offline on recorded frames before writing any real-time code.
- If the offline erase doesn't look convincing, keep the scenery-based fix and drop this.
