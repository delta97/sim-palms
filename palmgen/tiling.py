"""0.01 degree tile grid: index maths, tile ids named by the south-west corner, and file names.

All index maths is integer. A coordinate is first rounded to 1e-8 degree (about 1 mm), so float
noise such as ``-117.26000000000001`` lands on the grid edge it was meant to be on, and
``floor`` never sees ``-11726.000000000002``. A point less than 5e-9 degree from an edge is
therefore treated as lying on that edge.

Tile id format: ``<n|s><lat deg>p<2-digit frac>_<e|w><lon deg>p<2-digit frac>``, for example
``n32p78_w117p26`` (lat 32.78, lon -117.26 is the south-west corner). Negative coordinates name
the more negative edge: lat -0.005 is ``s0p01`` (tile south-west corner -0.01).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from typing import Final

from palmcore.geo import Bbox
from palmgen.errors import InputError

TILE_DEG: Final = 0.01

_ROUND_UNITS: Final = 100_000_000  # rounding granularity: 1e-8 degree per unit
_TILE_UNITS: Final = 1_000_000  # one tile: 0.01 degree = 1e6 units
_MAX_IX: Final = 18_000  # lon 180.00
_MAX_IY: Final = 9_000  # lat 90.00

_TILE_RE: Final = re.compile(r"([ns])(\d+)p(\d{2})_([ew])(\d+)p(\d{2})", re.ASCII)


def tile_index(lon: float, lat: float) -> tuple[int, int]:
    """Return ``(ix, iy)``: the south-west corner of the tile containing the point, in 0.01 deg."""
    if not (math.isfinite(lon) and math.isfinite(lat)):
        raise ValueError(f"lon and lat must be finite, got lon={lon!r} lat={lat!r}")
    ix = round(lon * _ROUND_UNITS) // _TILE_UNITS
    iy = round(lat * _ROUND_UNITS) // _TILE_UNITS
    return ix, iy


def _check_indices(ix: int, iy: int) -> None:
    if not -_MAX_IX <= ix <= _MAX_IX:
        raise ValueError(f"tile column ix={ix} is outside -{_MAX_IX}..{_MAX_IX}")
    if not -_MAX_IY <= iy <= _MAX_IY:
        raise ValueError(f"tile row iy={iy} is outside -{_MAX_IY}..{_MAX_IY}")


def tile_id(ix: int, iy: int) -> str:
    """Name of the tile whose south-west corner is at ``(ix, iy)``, e.g. ``n32p78_w117p26``."""
    _check_indices(ix, iy)
    lat_hemi = "n" if iy >= 0 else "s"
    lon_hemi = "e" if ix >= 0 else "w"
    lat_abs = abs(iy)
    lon_abs = abs(ix)
    return (
        f"{lat_hemi}{lat_abs // 100}p{lat_abs % 100:02d}"
        f"_{lon_hemi}{lon_abs // 100}p{lon_abs % 100:02d}"
    )


def parse_tile_id(tid: str) -> tuple[int, int]:
    """Invert :func:`tile_id`. Raises ``ValueError`` for anything that is not the canonical name."""
    match = _TILE_RE.fullmatch(tid) if isinstance(tid, str) else None
    if match is None:
        raise ValueError(f"not a tile id: {tid!r}")
    lat_hemi, lat_deg, lat_frac, lon_hemi, lon_deg, lon_frac = match.groups()
    iy = int(lat_deg) * 100 + int(lat_frac)
    ix = int(lon_deg) * 100 + int(lon_frac)
    if lat_hemi == "s":
        iy = -iy
    if lon_hemi == "w":
        ix = -ix
    _check_indices(ix, iy)
    if tile_id(ix, iy) != tid:
        raise ValueError(f"tile id {tid!r} is not in canonical form (expected {tile_id(ix, iy)!r})")
    return ix, iy


def tile_filename(tid: str) -> str:
    """Scene file name for a tile, e.g. ``tile_n32p78_w117p26.xml``."""
    parse_tile_id(tid)
    return f"tile_{tid}.xml"


def tile_bounds(tid: str) -> tuple[float, float, float, float]:
    """``(lon_min, lat_min, lon_max, lat_max)`` of a tile, in degrees."""
    ix, iy = parse_tile_id(tid)
    # Integer / 100.0 is correctly rounded, unlike a running sum of 0.01 steps.
    return (ix / 100.0, iy / 100.0, (ix + 1) / 100.0, (iy + 1) / 100.0)


def assign_polygon_tile(member_points: Mapping[str, tuple[float, float]]) -> str:
    """Tile of an exclusion polygon: the tile of its smallest ``palm_id``'s point.

    ``member_points`` maps ``palm_id`` to ``(lon, lat)``. The choice is deterministic and the
    point is always a polygon member, so the polygon stays near its tile.
    """
    if not member_points:
        raise InputError("cannot assign a tile to a polygon with no member points")
    palm_id = min(member_points)
    lon, lat = member_points[palm_id]
    return tile_id(*tile_index(lon, lat))


def check_bbox(bbox: Bbox | Sequence[float]) -> Bbox:
    """Validate a region bbox given as a ``Bbox`` or ``[lon_min, lat_min, lon_max, lat_max]``.

    Raises ``InputError`` for an antimeridian crossing (``lon_min > lon_max``), an out-of-range
    latitude or longitude, a degenerate box, or a wrong number of values.
    """
    if isinstance(bbox, Bbox):
        return bbox
    values = list(bbox)
    if len(values) == 4 and values[0] > values[2]:
        raise InputError(
            f"bbox lon_min ({values[0]!r}) is greater than lon_max ({values[2]!r}); "
            "a region that crosses the antimeridian is not supported"
        )
    try:
        return Bbox.from_list(values)
    except (TypeError, ValueError) as exc:
        raise InputError(f"invalid bbox {values!r}: {exc}") from exc
