"""``qa_rejects.csv``: every record or candidate that was dropped, with the reason (plan W10)."""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final

from palmscan.model import Reject

__all__ = ["METRIC_COLUMNS", "REJECT_COLUMNS", "reject_row", "sorted_rejects", "write_rejects_csv"]

METRIC_COLUMNS: Final = ("height_m", "crown_diam_m", "ratio", "shared_boundary_frac")
REJECT_COLUMNS: Final = (
    "stage",
    "source",
    "source_id",
    "lon",
    "lat",
    "reason",
    "all_reasons",
    "species_raw",
    *METRIC_COLUMNS,
)


def sorted_rejects(rejects: Iterable[Reject]) -> list[Reject]:
    """Rejects ordered by ``(stage, source, source_id)``; ties keep their input order."""
    return sorted(rejects, key=lambda r: (r.stage, r.source, r.source_id))


def _num(value: float | None, decimals: int) -> str:
    if value is None or not math.isfinite(value):
        return ""
    text = f"{value:.{decimals}f}"
    return "0" + text[2:] if text.startswith("-0") and float(text) == 0 else text


def reject_row(reject: Reject) -> list[str]:
    """One CSV row (strings, stable float formatting) in :data:`REJECT_COLUMNS` order."""
    return [
        reject.stage,
        reject.source,
        reject.source_id,
        _num(reject.lon, 7),
        _num(reject.lat, 7),
        reject.reason,
        ";".join(reject.all_reasons),
        reject.species_raw or "",
        *(_num(reject.metrics.get(name), 4) for name in METRIC_COLUMNS),
    ]


def write_rejects_csv(rejects: Sequence[Reject], path: Path) -> None:
    """Write the rejects as UTF-8 CSV with LF line ends, sorted; an empty list gives a header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(REJECT_COLUMNS)
        for reject in sorted_rejects(rejects):
            writer.writerow(reject_row(reject))
