# Labeling ground truth for palm accuracy tests

This guide tells you how to hand-label every palm you can see at one test site, in QGIS, and how to
get a file that `tests/accuracy/gt.py` accepts and the metrics script (TEST-010) can trust. It
needs no other document. The format reference is `plans/detailed/06-testing.md#ground-truth-format`.

Why this matters: the metrics measure how well palmscan's `palms.geojson` matches what a person
sees. A label you get wrong, or one copied from palmscan, makes every metric wrong in the same way.

## 1. Before you start

1. **The site must be defined.** Open `tests/sites/sites.yaml`. If the site's `status` is
   `placeholder`, stop: TEST-100 has to set its bbox first. `init-site` refuses placeholder sites.
2. **Label blind to the predictions.** Do not open `palms.geojson` (or any palmscan layer) while you
   label. You may open the palmscan CHM only after the height classes are done (section 5 explains
   why).
3. **Tools.** QGIS (LTR). QGIS version used: VERIFY on first labeling and record it in `meta.yaml`
   `notes`. Python with the project venv (`.venv`), used for `validate`.
4. **Imagery: USDA NAIP through WMS.** The service below answered its GetCapabilities request on
   2026-11-22 and lists the layer `USGSNAIPImagery:NaturalColor`:

   `https://imagery.nationalmap.gov/arcgis/services/USGSNAIPImagery/ImageServer/WMSServer`

   VERIFY: the layer draws at your site in QGIS. If it does not, use the Browser panel to find the
   service again (USGS National Map), and update the URL here and in `meta.yaml`.

   Record in `meta.yaml`: the imagery source (service and layer), the **capture date** of the tiles
   you labelled on, and the ground sample distance in metres (NAIP is typically 0.6 m; VERIFY for
   the tiles you see). Where you read the capture year in QGIS is VERIFY on first use.

5. **Time budget.** About 2 minutes per palm, including the species lookup. Plan on about 100 palms
   at each of T1 and T2, and every palm at T4 (the false-positive site). That is about 3.5 hours per
   100-palm site, so split it into sessions and log each one in the task file.

## 2. Files for one site

Everything lives in `tests/accuracy/<site>/` (for example `tests/accuracy/T1/`):

| File | Who writes it | Contents |
|---|---|---|
| `ground_truth.geojson` | you, in QGIS | one Point per palm, EPSG:4326 |
| `labeled_area.geojson` | created by `init-site`; shrink it in QGIS only if you did not sweep all of it | the swept polygon |
| `meta.yaml` | created by `init-site`; you fill it in | imagery, labellers, dates, notes |

Keep the QGIS project file outside the repository (or in `data/`, which is gitignored). Commit only
the three files above, on the task branch.

## 3. Step by step

### Step 1: create the skeleton

```bash
python -m tests.accuracy.gt init-site T1
```

This writes an empty `ground_truth.geojson`, `labeled_area.geojson` from the site bbox, and a
`meta.yaml` with `TBD` placeholders. It refuses to overwrite an existing folder.

### Step 2: set up QGIS

1. New project. Project CRS: EPSG:4326 (Project > Properties > CRS).
2. Add the NAIP imagery: Layer > Add Layer > Add WMS/WMTS Layer. Use the URL in section 1 and the
   layer `USGSNAIPImagery:NaturalColor`. Zoom to the site.
3. Optional: add a street basemap for orientation. It is not a labelling source.

### Step 3: load the layers

1. Add `tests/accuracy/<site>/labeled_area.geojson`. Style it as an outline so you can see the edge.
2. Add `tests/accuracy/<site>/ground_truth.geojson` and toggle editing on.

### Step 4: set the attribute widgets

For each enum field, open the layer's Properties > Attributes Form, select the field, and set the
widget type to **Value Map** with these values. Text fields stay as text. VERIFY the menu names on
your QGIS version.

| Field | Widget | Values |
|---|---|---|
| `height_class` | Value Map | `S`, `M`, `T`, `X`, `unknown` |
| `species_basis` | Value Map | `inventory`, `streetview`, `imagery`, `unknown` |
| `context` | Value Map | `street`, `beach`, `park`, `yard`, `parking`, `other` |
| `confidence` | Value Map | `high`, `low` |
| `species` | Text | a species key, or `unknown` (see below) |
| `gt_id` | Text, read only if you can | see below |
| `note` | Text | optional |
| `height_ref_m` | leave alone | written later by `fill-heights` |

Do not add other fields. `validate` rejects any property it does not know, so when you save
(step 9) untick any extra field QGIS added.

**`gt_id`.** Run `python -m tests.accuracy.gt next-id <site>` and type the printed id. Then use the
next number for each new palm, in order. Ids must be unique: `validate` reports duplicates.

**`species`.** Use the key form `genus_species`, lowercase, for example `washingtonia_robusta` or
`washingtonia_filifera`. A genus-level key is `<genus>_sp`, for example `washingtonia_sp`. Use
`unknown` when you cannot tell. The canonical list will be `palmscan/data/species_keys.yaml`
(SCAN-002, not yet merged): once it is on main, use only keys from that file. VERIFY.

### Step 5: label, strip by strip

1. Zoom to about 1:500. Work **north to south** in strips about one screen tall. Overlap each strip
   with the previous one so nothing is missed.
2. Sweep the strip edge to edge inside `labeled_area`. When you finish a strip, note its name or
   row in `meta.yaml` `notes` only if the sweep is incomplete.
3. For every palm you see, add one point (see the placement rules below) and fill in its
   properties before you move on. Do not leave blank fields for later.
4. If you cannot finish the whole area in one session, stop with a clear boundary. Later, in QGIS,
   shrink `labeled_area` to the part you swept, and write in `notes` which part you skipped and why.
   Every point must stay inside the area, or `validate` fails.

**Placement rules (crown centre):**

- Put the point at the **centre of the crown** as seen in the orthoimage: the middle of the frond
  spread, seen from above. This is the position palmscan's `palms.geojson` is compared with.
- **Two palms with overlapping crowns:** if you can see two crown centres, one point each. If you
  cannot separate them, one point at the centre of the combined crown with `confidence: low` and a
  note such as `cluster of 2?`.
- **Palm partly under a building, tree or shadow:** point at the visible crown centre estimate. If
  less than about half the crown is visible, `confidence: low`.
- **Trunk with no visible crown** (cut stub, dead palm with no fronds): not a palm for this test;
  do not label it.
- **A palm you suspect but cannot confirm:** `confidence: low`. Use `low` only for "maybe a palm".
  An unmatched low point is ignored by the metrics, not counted as a miss.

**Field rules:**

- `context`: where the palm stands. `street` (verge or median along a road), `beach` (sand or
  boardwalk), `park`, `yard` (residential lot), `parking` (lot or median in a car park), `other`.
- `confidence`: `high` when you would bet it is a palm. `low` otherwise (see above).
- `height_class`: judge the height from the orthoimage: shadow length, crown size against
  neighbours, and the scale of nearby buildings or cars. Use the class edges below. Use `unknown`
  when you cannot judge; `unknown` points are still counted for position and species.

  | Class | Height |
  |---|---|
  | `S` | under 8 m |
  | `M` | 8 m to under 15 m |
  | `T` | 15 m to under 25 m |
  | `X` | 25 m or more |

- `species` and `species_basis`: see step 6. `species_basis` says where the species label came from.
- `note`: free text, for anything a reviewer must know (for example "shadowed, crown partly hidden").

### Step 6: species, without copying predictions

Pick the **first** source that applies, and record it in `species_basis`:

| `species_basis` | Use when |
|---|---|
| `inventory` | you looked up this palm in a tree inventory record you can open (a city or county street-tree layer), and it names the species. Record the record id in `note` if you can. |
| `streetview` | you identified the species from street-level imagery (Street View or similar). Record the imagery date in `note`. |
| `imagery` | you identified it from the orthoimage alone (crown shape, colour, trunk visible). |
| `unknown` | none of the above. Then `species` must be `unknown` too. |

Rules:

- **Never** copy the species from a palmscan prediction, from `palms.geojson`, or from a previous
  run. `species_basis` tells the metrics where each label came from, and a copied label would make
  the species accuracy meaningless.
- `species` and `species_basis` must agree: both `unknown`, or both known. `validate` checks this.

### Step 7: height from the CHM (optional, after the classes)

The CHM is a palmscan output (Phase 4, SCAN-101). If it exists, `fill-heights` writes
`height_ref_m`, the CHM maximum within 1.5 m of each point. This checks palmscan's height extraction.
It is not an independent height measurement.

Do the `height_class` pass from imagery first. Load the CHM only after that, and say in `meta.yaml`
notes whether you looked at the CHM before labelling heights. The metrics treat height-class
agreement as the independent human check, so this matters.

### Step 8: meta.yaml

Open `tests/accuracy/<site>/meta.yaml` and fill in:

- `imagery.source`: the service and layer you used (section 1).
- `imagery.date`: the capture date of the tiles, `YYYY-MM-DD`.
- `imagery.resolution_m`: the ground sample distance, in metres.
- `labelers`: your name or initials, as a list.
- `labeled_on`: the date labelling finished, `YYYY-MM-DD`.
- `notes`: the QGIS version, the area swept (full or partial), and anything a reviewer must know.

Do not leave any `TBD` in the file. `validate` reports every one.

### Step 9: save from QGIS

1. Layer > Save Features As, for `ground_truth.geojson`:
   - Format: GeoJSON.
   - File name: `tests/accuracy/<site>/ground_truth.geojson`. Overwrite.
   - CRS: EPSG:4326.
   - Coordinate precision: **7 decimal places**. VERIFY the option name in your QGIS version (GDAL
     GeoJSON `COORDINATE_PRECISION`, or the RFC 7946 option).
   - Fields: only `gt_id`, `height_class`, `height_ref_m` (if present), `species`, `species_basis`,
     `context`, `confidence`, `note`.
2. If you shrank the area, save `labeled_area.geojson` the same way: one polygon, EPSG:4326.
3. Do not save over the files while another program has them open.

### Step 10: validate

```bash
python -m tests.accuracy.gt validate <site>
```

It prints the counts by `context`, `confidence`, `height_class` and `species`, then `OK` or a list of
problems. Exit code 0 means it passed; 1 means a problem in the data; 2 means a file is missing or
unreadable. Fix each problem in QGIS, save again, and run `validate` again until it passes.

Commit the three files on the task branch when `validate` passes.

## 4. Common problems and fixes

| `validate` says | Fix |
|---|---|
| `duplicate gt_id` | Two points share an id. Give the later one `next-id`. |
| `point is outside labeled_area.geojson` | Move the point inside the swept area, or shrink the area if you did not sweep there. |
| `is not one of [...]` | An enum value is misspelt or not in the list. Use the Value Map. |
| `species ... and species_basis ... disagree` | Both `unknown`, or both known. |
| `has more than 7 decimals` | Save again with coordinate precision 7. |
| `still TBD` | Fill that field in `meta.yaml`. |
| `labelers is empty` / `labeled_on is not set` | Fill them in once there are points. |
| `must hold exactly one feature` (area) | Keep one polygon in `labeled_area.geojson`. |
| `Additional properties are not allowed` | Remove the extra field before saving (step 9). |

## 5. Quick rules to remember

- Label blind: no predictions, no palmscan layers, while you label.
- One point per palm, at the crown centre.
- `low` means "maybe a palm", not "hard to size".
- Species come from an inventory, a street photo, or the orthoimage, never from palmscan.
- Every point inside the swept area.
- Validate before you commit.

## 6. Open items (VERIFY)

- The NAIP layer draws at your site and its capture date can be read in QGIS (section 1).
- QGIS version used, and the exact menu names for Value Map and the coordinate precision option
  (steps 4 and 9).
- Canonical species keys: once `palmscan/data/species_keys.yaml` is on main, the `species` check must
  use it (SCAN-002). Until then the check is the pattern `genus_species`, or `unknown`.
