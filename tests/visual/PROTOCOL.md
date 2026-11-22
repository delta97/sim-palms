# In-sim visual test protocol

Use this to check, by eye on the Windows sim PC, that the palm fix removes the green blobs and puts
believable palms in their place. You need MSFS 2024, the test site's region package, and the fix
package. The tools in this folder make each run repeatable and keep a log. They never take
screenshots or judge the result for you.

Plan: `plans/detailed/06-testing.md#visual-protocol`. Checklist items: `checklist_template.md`.

## Before you start

1. Tools: from the repo root, `python -m venv .venv` then `.venv/Scripts/python -m pip install -e ".[dev]"`
   (Pillow is in the `dev` extra; `finalize` needs it).
2. Sites: pick the site id from `tests/sites/sites.yaml` (T1 to T5). Each site's bbox, viewpoints,
   time and weather are there. A site marked `status: placeholder` is not defined yet: the tools
   refuse it. TEST-100 (sim PC) defines the sites first.
3. Viewpoints (fixed for every run):
   - VP1 street, about 2 m above ground
   - VP2 low oblique, about 150 m
   - VP3 approach, about 600 m

   Recall each viewpoint from its entry in `tests/sites/sites.yaml` (lat, lon, altitude, heading,
   pitch). Method for placing the camera or aircraft at them, and for reloading the same flight:
   VERIFY: TEST-006 (`docs/findings/TEST-006.md`) and TEST-100 (recorded per viewpoint in `preset`).
   Do not guess a method; if the findings are not there yet, stop and say so.
4. Graphics: profile `ref-v1` in `graphics_profile.yaml`. Local time 12:00, clear weather. Set
   everything in the profile by hand. Write any setting you cannot match in `run.yaml`
   `deviations`, with its value.

## Steps

**1. Create the run folder.** From the repo root:

```bash
python -m tests.visual.new_run --site T1 --label phase2 --sim-version <sim version> --region-pkg <region package version>
```

Add `--variants nofix,static` (the default) or `live` when that variant is in use. This makes
`tests/visual/T1/<date>_phase2/` with `run.yaml`, `checklist.md` and `raw/<variant>/`, and adds a
`pending` row to `test_log.md`. Fill in `tester` and `sdk_version` in `run.yaml` by hand; they are
`VERIFY` until you do.

**2. Set up the sim.** Load the graphics profile, 12:00 local time, clear weather. Note any
deviation in `run.yaml`.

**3. No-fix pass.** Deactivate the fix package. Load the site's flight (VERIFY: flight file or
saved-flight method, TEST-006). Visit VP1, VP2 and VP3 in that order and take one screenshot at
each. Copy the screenshots into `raw/nofix/`. Keep the capture order: the first screenshot is VP1,
the second VP2, the third VP3.

**4. Fix pass.** Activate the fix package. Restart the sim if the community package loads only at
startup (VERIFY: TEST-006). Repeat step 3 into `raw/static/`.

**5. Finalize.** For each variant, the tool takes the three screenshots in order and writes
`VP1_street.jpg`, `VP2_oblique.jpg`, `VP3_approach.jpg` (JPEG q90, max 2560 px wide):

```bash
python -m tests.visual.new_run finalize tests/visual/T1/<date>_phase2
```

It orders each folder by file modification time. If two screenshots share a time it stops, so
rename the raw files in capture order (`01.png`, `02.png`, `03.png`) and rerun with
`--order name`. Check the printed mapping against what you saw.

**6. Fill the checklist.** Open `checklist.md` and compare the `nofix` and `static` images side by
side. For each check (C1 to C8) and each viewpoint write `pass`, `fail` or `na`. Leave no cell
blank. Put what you saw in Notes, with the file names.

- C8 (species) is `na` everywhere before Phase 3, because the stand-in trees are not species.
- A run passes when no cell is `fail` and no cell is blank.

**7. Check and record.**

```bash
python -m tests.visual.check_run tests/visual/T1/<date>_phase2 --update-log
```

Exit 0 means pass. Exit 1 lists the problems: a missing image, a blank or invalid cell, or a
`fail` cell. `--update-log` sets the run's Result in `test_log.md` to `pass` or `fail`. An
incomplete run with no failed cell stays `pending`.

## Storage

- Raw screenshots in `raw/` are gitignored (`tests/visual/.gitignore`). Keep them on your PC.
- Finalized JPEGs, `run.yaml` and `checklist.md` are committed in plain git. VERIFY: whether
  DEC-008 (ADR-0009) moves screenshots to Git LFS; if it does, only this wording changes.
- Findings from a run that need a write-up go in `docs/findings/<TASK-ID>.md`.

## Rules

- Never fill in a cell for a check you did not look at. A run needs the sim, so a result made on
  another machine is not a result.
- Never edit a finished run's images or checklist to make it pass. If a run is wrong, make a new
  run with a new label.
- Scores from TEST-008 (`diff_score`), if present, flag changes for a person to look at. They do
  not pass or fail a run.
