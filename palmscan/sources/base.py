"""Inventory adapter interface shared by every palmscan source adapter.

Adapters return raw :class:`~palmscan.model.TreeRecord` values inside the bbox only. They
never normalise species names; that is the job of the ingest stage.
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Protocol

from palmcore.errors import SourceError
from palmscan.cache import Cache
from palmscan.geo import Bbox
from palmscan.http import HttpClient
from palmscan.model import SourceVintage, TreeRecord

__all__ = [
    "FetchResult",
    "InventoryAdapter",
    "SourceError",
    "as_bbox",
    "derive_vintage",
    "parse_date",
]

_US_DATE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_YEAR_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_YEAR = re.compile(r"^(\d{4})$")
_EPOCH_MS = re.compile(r"^-?\d{9,}(\.\d+)?$")
# Epoch milliseconds for years 1900..2200: anything outside is not a plausible record date.
_MIN_EPOCH_MS = -2_208_988_800_000
_MAX_EPOCH_MS = 7_258_118_400_000


@dataclass(slots=True)
class FetchResult:
    """What an adapter returns: records inside the bbox, their vintage, and warnings."""

    records: list[TreeRecord]
    vintage: SourceVintage
    warnings: list[str] = field(default_factory=list)


class InventoryAdapter(Protocol):
    """A tree-inventory source. ``name`` is the config source name."""

    name: str

    def fetch(self, bbox: Bbox | Sequence[float], cache: Cache, http: HttpClient) -> FetchResult:
        """Return the raw records inside ``bbox`` (``lon_min, lat_min, lon_max, lat_max``)."""
        ...


def as_bbox(bbox: Bbox | Sequence[float]) -> Bbox:
    """Accept a :class:`Bbox` or a 4-sequence ``[lon_min, lat_min, lon_max, lat_max]``."""
    return bbox if isinstance(bbox, Bbox) else Bbox.from_list(bbox)


def _epoch_ms_to_date(ms: float) -> date | None:
    if not _MIN_EPOCH_MS <= ms <= _MAX_EPOCH_MS:
        return None
    return datetime.fromtimestamp(ms / 1000.0, tz=UTC).date()


def parse_date(value: Any) -> date | None:
    """Parse a record date; ``None`` when it cannot be read.

    Accepts ISO 8601 text (``2021-03-04``, ``2021-03-04T10:00:00Z``, ``2021-03`` and ``2021``;
    partial dates become the first day), ``MM/DD/YYYY``, epoch milliseconds (number or digit
    string of 9+ digits), and ``date``/``datetime`` objects.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        if value != value:  # NaN
            return None
        return _epoch_ms_to_date(float(value))
    text = str(value).strip()
    if not text:
        return None
    if _EPOCH_MS.match(text):
        return _epoch_ms_to_date(float(text))
    m = _US_DATE.match(text)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None
    m = _YEAR_MONTH.match(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), 1)
        except ValueError:
            return None
    m = _YEAR.match(text)
    if m:
        year = int(m.group(1))
        return date(year, 1, 1) if year >= 1 else None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def derive_vintage(
    cfg_vintage: str | None,
    record_dates: Iterable[Any],
    layer_edit_ms: int | float | None,
    fetched_at: datetime,
    *,
    source: str = "",
) -> SourceVintage:
    """Work out a source's vintage. Precedence: config, record dates, layer edit date, fetch.

    - config ``vintage`` string wins (basis ``config``);
    - else the median year of the parseable ``record_dates`` (basis ``record_dates``; raw
      values are parsed with :func:`parse_date`, an even count takes the lower median);
    - else the year of ``layer_edit_ms`` (epoch ms, basis ``layer_edit_date``);
    - else ``fetched_at`` as ``YYYY-MM`` (basis ``fetched``).

    ``fetched_at`` is stored as an ISO 8601 UTC string (naive values are taken as UTC).
    """
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    fetched_utc = fetched_at.astimezone(UTC)
    fetched_iso = fetched_utc.isoformat(timespec="seconds").replace("+00:00", "Z")

    if cfg_vintage is not None and str(cfg_vintage).strip():
        return SourceVintage(source, str(cfg_vintage).strip(), "config", fetched_iso)

    years = [d.year for d in map(parse_date, record_dates) if d is not None]
    if years:
        return SourceVintage(
            source, f"{statistics.median_low(years):04d}", "record_dates", fetched_iso
        )

    if layer_edit_ms is not None:
        edited = parse_date(layer_edit_ms)
        if edited is not None:
            return SourceVintage(source, f"{edited.year:04d}", "layer_edit_date", fetched_iso)

    return SourceVintage(source, fetched_utc.strftime("%Y-%m"), "fetched", fetched_iso)
