# Visual test log

One row per in-sim visual run. Append-only: `python -m tests.visual.new_run` adds a `pending`
row, and `python -m tests.visual.check_run <run_dir> --update-log` sets its Result to `pass` or
`fail`. Do not hand-edit rows. Run folders are `tests/visual/<site>/<date>[_<label>]/`
(protocol: [PROTOCOL.md](PROTOCOL.md)).

Result is `pending`, `pass` or `fail`.

| Date | Site | Label | Variants | Sim version | Region pkg | Result | Run folder |
|---|---|---|---|---|---|---|---|
