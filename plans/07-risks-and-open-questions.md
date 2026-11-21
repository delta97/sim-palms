# 07. Risks and Open Questions

## Summary

The biggest risk is outside your control: Exclude TIN depends on the sim and has broken before. Phase 0 and the regression routine exist to catch that early. The second biggest risk is visual quality of the palm models.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Exclude TIN or vegetation exclude broken on the current update | Medium | Blocks the project | Phase 0 confirms it first; regression routine after each update; report bugs on DevSupport |
| Cuts leave ugly ground (seams, hole edges) | Medium | Hurts visual quality | Tune margin small; test at three viewpoints; merge nearby cuts so there are fewer edges |
| Cuts damage nearby buildings | Medium | Visible defects | Clip cuts by building footprints; dedicated test site T3 |
| Data out of date (palms removed or planted since inventory or LiDAR) | High in places | Leftover blobs, or palms with no blob (harmless: a real palm still stands there) | Combine sources; record data vintage; QA map shows stale areas |
| Bing photogrammetry date differs from tree data date | Medium | Occasional mismatches | Accept a small miss rate; spot-check during scale-out |
| Private-yard palms missing from inventories | High | Leftover blobs in residential areas | LiDAR detection in Phase 4 |
| False positives (Italian cypress, poles, chimneys) | Medium | Palms where none exist | Building filter, crown-size rule, test site T4 |
| Hand-written XML rejected or subtly wrong | Medium | Build errors or missing objects | Templates copied from Scenery Editor output; golden-file tests |
| `fspackagetool` slow, or can't run with the sim open | Medium | "On demand" becomes "before launch" | Measured in Phase 0; data is static, so prebuilding regions is fine |
| Too many objects hurt performance | Medium | Lower FPS | LOD budgets; static vs live bake-off; spawn cap |
| SimConnect live objects leak or cost too much CPU | Medium | Stutter, leftover objects | Default to static; cleanup logic; soak test |
| Palm models look wrong or cheap | Medium | The fix looks worse than expected | One species first, review, then the rest; consider licensing |
| Conflicts with other mods or airports | Medium | Duplicates or clashes | `mask_out` areas; airport masks by default |
| Licensing if published (tree data, OSM, models) | Low for personal use, medium if published | Takedown or legal trouble | Check each source and model license before publishing; credit OSM (ODbL) |

---

## Open questions for you

1. **Personal use or publish?** Publishing on flightsim.to means checking every data and model license, and adds support work.
2. **Build or license the palm models?** Building is 20–40 hours; licensing is faster but has terms to check.
3. **Companion app language:** C# is the plan because SimConnect support is best there. Say so if you'd rather stay in Python and accept a thinner, community-maintained SimConnect binding.
4. **First test block:** which San Diego or LA street do you know well enough to judge?
5. **Performance budget:** what GPU and settings do you fly with? The 5% frametime budget may need to change.
6. **Scope beyond palms:** the same pipeline could handle other blob trees (for example Italian cypress, eucalyptus). Out of scope for now; worth deciding after Phase 3.

---

## Recap

- Phase 0 tests the biggest risk first.
- Data gaps are expected; LiDAR and QA maps reduce them.
- Several decisions are yours, starting with whether this stays personal or gets published.
