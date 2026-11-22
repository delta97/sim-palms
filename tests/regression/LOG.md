# Regression log

One row per sim or SDK update, newest at the bottom. Run the routine in [ROUTINE.md](ROUTINE.md) when a trigger in `docs/process/sim-update-watch.md` fires, or when the sim or SDK updates on the user's PC. The first run is TEST-104; until it runs, this table has no rows.

Add a row with `python -m tests.regression.new_entry` and change cells with its `set` subcommand. Do not hand-edit rows.

Cells: `pass`, `fail`, `skip`, `pending`. Trigger: `SU`, `hotfix`, `beta`, `SDK`. The Notes column links to `runs/<date>/notes.md`.

| Date | Trigger | Sim version | SDK version | R1 single blob | R2 rebuild | R3 visual T1 | R3 visual T3 | R4 full suite | Result | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
