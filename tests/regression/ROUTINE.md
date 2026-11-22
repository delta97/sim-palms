# Post-update regression routine

Run this after every MSFS 2024 sim update, SDK update, hotfix or beta build that reaches the user's PC, and whenever a trigger in `docs/process/sim-update-watch.md` fires. It catches blobs that come back, broken builds and visual drift on the same day as the update. Results go in [LOG.md](LOG.md), one row per update.

Written by TEST-015. TEST-104 runs it the first time and writes the first baseline row. The watch log's "TEST-104 run reference" column takes the LOG.md row, written as `tests/regression/LOG.md <date> <trigger>` (or `pending` until the row exists).

## Rules

- Steps 1 and 3 need the sim on the user's Windows PC. Do not fill those cells from another machine or from a screenshot you did not take yourself. If the sim is not available, leave the cell `pending` and say so in the notes.
- Never mark a check `pass` without evidence paths in the run notes. A tool that does not exist yet (TEST-016, TEST-008, TEST-102, TEST-103 not merged) means the step cannot run: keep the cell `pending`, not `pass`.
- Installed sim and SDK versions are read from the user's PC (VERIFY: exact menu path, TEST-104). Public version numbers from web pages are not the installed version. Use `VERIFY` in the version field until then.
- Sites are referred to by id from the registry (`tests/sites/sites.yaml`, loaded by `tests/helpers/sites.py`). Do not type coordinates into a run. Sites are `placeholder` until TEST-100 defines them; tools refuse placeholder sites, so R3 cannot run before TEST-100 is done.
- Times below are rough estimates, not measured. Record the real times in the notes.

Look up the region of a site with:

```bash
python -c "from tests.helpers.sites import get_site; s = get_site('T1'); print(s.region, s.status)"
```

Use the same call with `T3` for the second visual site.

## Step 0. Add the row (under 1 minute)

```bash
python -m tests.regression.new_entry --trigger SU --sim-version <v> --sdk-version <v>
```

Use `--trigger` `SU`, `hotfix`, `beta` or `SDK`. Add `--date YYYY-MM-DD` only for a back-filled run. This appends a row with every check `pending` and creates `tests/regression/runs/<date>/notes.md` from its template. It refuses a second row for the same date and trigger.

Pass: exit 0, one new row in LOG.md, notes file present. Refused: a row already exists, so use `set` below instead of adding another.

## Step 1. R1 single blob (sim, about 30 to 45 minutes, estimate)

1. Open the Phase 0 project. Its path comes from the Phase 0 findings (VERIFY in TEST-104).
2. Build it in Dev Mode with the current sim and SDK.
3. Check the scene at street level and at 150 m above ground, at the T1 site (load it through the TEST-102 flight, see step 3).
4. Pass: the photogrammetry blob is cut where the package says, and the stand-in palm is visible. Fail: the blob is not cut, or no stand-in shows.
5. Write what you saw and a screenshot path in the notes. Then:

```bash
python -m tests.regression.new_entry set <date> R1 pass --trigger <trigger>
```

(Use `fail` or `skip` as needed. `skip` needs a reason in the notes.)

## Step 2. R2 rebuild (about 10 to 60 minutes, estimate; depends on region)

```bash
palmgen build --region <region-of-T1>
python -m tests.regression.check_build build/palmfix-<region> --palms build/scan/<region>/palms.geojson --append-history
```

- `<region-of-T1>` is the `region` printed by the lookup above (currently `san-diego-coastal` in the registry).
- Pass: `palmgen build` finishes and `check_build` exits 0. `--append-history` adds a line to `tests/regression/build_history.csv`.
- Record the build report path and the exit codes in the notes.

```bash
python -m tests.regression.new_entry set <date> R2 pass --trigger <trigger>
```

## Step 3. R3 visual at T1 and T3 (sim, about 45 to 60 minutes per site, estimate)

Follow `tests/visual/PROTOCOL.md` (TEST-102). Variants are `nofix,static`.

1. `python -m tests.visual.new_run --site T1 --label regression-<date> --sim-version <v> --region-pkg <ver> --variants nofix,static`
2. Sim: graphics profile `ref-v1` from `tests/visual/graphics_profile.yaml`, local time 12:00, clear weather. Note deviations in `run.yaml`.
3. Deactivate the fix package for `nofix`. Load the site's flight, visit VP1, VP2, VP3 in order, one screenshot each, into `raw/nofix/`. Activate the fix package and repeat into `raw/static/`.
4. `python -m tests.visual.new_run finalize <run_dir>`, then confirm the image mapping it prints.
5. Fill `checklist.md` by comparing the two variants side by side.
6. `python -m tests.visual.check_run <run_dir> --update-log`. Pass = exit 0 (images present, checklist complete, `pass` written to the visual log).
7. Repeat steps 1 to 6 for T3.

Optional, when TEST-008 is merged: `python -m tests.visual.diff_score <run_a> <run_b> --variant static --write` against the last passing run, and note any flags. A flag is not a fail on its own.

```bash
python -m tests.regression.new_entry set <date> R3-T1 pass --trigger <trigger>
python -m tests.regression.new_entry set <date> R3-T3 pass --trigger <trigger>
```

## Step 4. R4 full suite (only if needed)

Run it only if R1, R2 or R3 has any `fail`, or a `diff_score` flag you judge to be a real change. Otherwise set `skip` with the reason "R1 to R3 pass, no flags".

If run: visual protocol (step 3) at T1 to T5, plus the performance flight from TEST-103 (`tests/perf/PROCEDURE.md`), compared with the last report with `python -m tests.perf.compare tests/perf/runs/<id>`.

```bash
python -m tests.regression.new_entry set <date> R4 pass --trigger <trigger>
```

## Step 5. Fill the result

Set `Result` to `pass` when R1, R2, R3-T1 and R3-T3 pass and R4 is `pass` or `skip`. Set `fail` if any check failed. Otherwise leave it `pending`.

```bash
python -m tests.regression.new_entry set <date> Result pass --trigger <trigger>
```

Then add the LOG.md row reference to the watch log's last column in `tracking/logs/sim-update-watch.md`.

### If anything fails

1. Deactivate the region packages (the fix package and any region package from `regions/`), so the user's sim runs without them.
2. Check DevSupport for a known issue with the same symptom. Search the terms in `docs/process/sim-update-watch.md` (for example `exclude TIN`, `exclusion`, `vegetation exclude`, `photogrammetry`). Note the thread URL and its status tag.
3. If no report matches, file a bug report on DevSupport with the sim and SDK versions, the steps, and the screenshots. Record the URL in the notes.
4. Log the failure in the RISK area: add a line to the risk register in `plans/detailed/07-risks-and-open-questions.md` (or a new RISK task) and link the LOG.md row. An R1 fail on exclusions is kill criterion K1 (K9 for an active or released package); say so.
5. Do not rebuild the fix to chase a failure during the regression run. The routine records what the update did. Fixes are separate tasks.

## Quick reference

| Step | Who | Needs | Pass means |
|---|---|---|---|
| 0 | anyone | Python | row and notes file exist |
| 1 R1 | user, on the sim PC | sim, Phase 0 project | blob cut, stand-in visible at 2 m and 150 m |
| 2 R2 | anyone with the repo | palmgen, scan output | build finishes, `check_build` exit 0 |
| 3 R3 | user, on the sim PC | sim, TEST-102 tooling, TEST-100 sites | `check_run` exit 0 for T1 and T3 |
| 4 R4 | user, only if needed | sim, TEST-103 perf flight | every threshold in the perf and visual protocols passes |
| 5 | anyone | LOG.md | `Result` set |

Exit codes for the `new_entry` commands: 0 ok, 2 bad input or refusal.
