"""Cross-check: FX-008 ingest reads sessions written by the FX-004 synthetic generator.

The two tasks were built in parallel against placeholder capture formats (VERIFY until
FX-001/FX-006/FX-007); this test keeps the generator and the ingest in step.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from palmfx.offline.ingest import ingest
from palmfx.offline.session import open_session


def test_ingest_reads_synthetic_session(synth_session_dir: Path, tmp_path: Path) -> None:
    root = tmp_path / "session"
    shutil.copytree(synth_session_dir, root)
    meta = json.loads((root / "session.json").read_text(encoding="utf-8"))
    offset_ms = float(meta["synthetic"]["time_offset_ms"])
    # The generator must name its screenshot suffixes the way ingest reads them.
    assert set(meta["reshade_suffixes"]) == {"before", "after"}

    n = ingest(open_session(root), offset_ms=offset_ms)

    records = [
        json.loads(line)
        for line in (root / "frames.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert n == len(records) > 0
    assert all(r["pose"] is not None for r in records)
    assert [r["idx"] for r in records] == sorted(r["idx"] for r in records)
    for r in records:
        # Metric "depth" stays null until calibration (FX-009) fits the depth model.
        for key in ("color", "depthraw"):
            assert (root / r[key]).is_file(), r[key]
