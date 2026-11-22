"""Geo helpers shared by palmscan and palmgen.

Conventions: coordinates are always (lon, lat) / (x, y); all transforms use ``always_xy=True``.
Limitations: the antimeridian is not supported (a ``Bbox`` never wraps), and the UTM zone
selection has no Norway/Svalbard exceptions.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import pyproj

WGS84: Final = "EPSG:4326"
EARTH_RADIUS_M: Final = 6_371_008.8


@dataclass(frozen=True)
class Bbox:
    """A WGS84 bounding box (lon_min, lat_min, lon_max, lat_max), in degrees.

    The antimeridian is not supported: ``lon_min`` must be strictly less than ``lon_max``.
    """

    lon_min: float
    lat_min: float
    lon_max: float
    lat_max: float

    def __post_init__(self) -> None:
        for name in ("lon_min", "lat_min", "lon_max", "lat_max"):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise ValueError(f"Bbox {name} must be finite, got {value!r}")
        for name in ("lon_min", "lon_max"):
            value = getattr(self, name)
            if not -180.0 <= value <= 180.0:
                raise ValueError(f"Bbox {name} must be within -180..180, got {value!r}")
        for name in ("lat_min", "lat_max"):
            value = getattr(self, name)
            if not -90.0 <= value <= 90.0:
                raise ValueError(f"Bbox {name} must be within -90..90, got {value!r}")
        if self.lon_min >= self.lon_max:
            raise ValueError(
                f"Bbox lon_min ({self.lon_min!r}) must be less than lon_max ({self.lon_max!r})"
            )
        if self.lat_min >= self.lat_max:
            raise ValueError(
                f"Bbox lat_min ({self.lat_min!r}) must be less than lat_max ({self.lat_max!r})"
            )

    @classmethod
    def from_list(cls, values: Sequence[float]) -> Bbox:
        """Build from exactly four numbers: lon_min, lat_min, lon_max, lat_max."""
        if len(values) != 4:
            raise ValueError(f"Bbox needs exactly 4 values, got {len(values)}")
        lon_min, lat_min, lon_max, lat_max = (float(v) for v in values)
        return cls(lon_min, lat_min, lon_max, lat_max)

    def to_list(self) -> list[float]:
        return [self.lon_min, self.lat_min, self.lon_max, self.lat_max]

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.lon_min, self.lat_min, self.lon_max, self.lat_max)

    def contains(self, lon: float, lat: float) -> bool:
        """True if the point is inside or on an edge."""
        return self.lon_min <= lon <= self.lon_max and self.lat_min <= lat <= self.lat_max

    def intersects(self, other: Bbox) -> bool:
        """True if the boxes overlap; touching edges count."""
        return (
            self.lon_min <= other.lon_max
            and other.lon_min <= self.lon_max
            and self.lat_min <= other.lat_max
            and other.lat_min <= self.lat_max
        )

    def center(self) -> tuple[float, float]:
        """Centre as (lon, lat)."""
        return ((self.lon_min + self.lon_max) / 2.0, (self.lat_min + self.lat_max) / 2.0)

    def buffer_m(self, meters: float) -> Bbox:
        """Grow each side by ``meters`` (converted to degrees at the centre latitude).

        The result is clamped to +-180 / +-90.
        """
        lon_m, lat_m = meters_per_degree(self.center()[1])
        dlon = meters / lon_m
        dlat = meters / lat_m
        return Bbox(
            max(-180.0, self.lon_min - dlon),
            max(-90.0, self.lat_min - dlat),
            min(180.0, self.lon_max + dlon),
            min(90.0, self.lat_max + dlat),
        )

    def width_m(self) -> float:
        """East-west extent in metres at the centre latitude."""
        return (self.lon_max - self.lon_min) * meters_per_degree(self.center()[1])[0]

    def height_m(self) -> float:
        """North-south extent in metres at the centre latitude."""
        return (self.lat_max - self.lat_min) * meters_per_degree(self.center()[1])[1]


def haversine_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def meters_per_degree(lat: float) -> tuple[float, float]:
    """Return (metres per degree of longitude, metres per degree of latitude) at ``lat``."""
    phi = math.radians(lat)
    lat_m = (
        111132.92
        - 559.82 * math.cos(2.0 * phi)
        + 1.175 * math.cos(4.0 * phi)
        - 0.0023 * math.cos(6.0 * phi)
    )
    lon_m = 111412.84 * math.cos(phi) - 93.5 * math.cos(3.0 * phi) + 0.118 * math.cos(5.0 * phi)
    return (lon_m, lat_m)


def utm_epsg(lon: float, lat: float) -> int:
    """EPSG code of the UTM zone containing the point (326zz north, 327zz south).

    No Norway/Svalbard exceptions; the antimeridian is not handled specially (lon 180 is zone 60).
    """
    zone = min(60, max(1, math.floor((lon + 180.0) / 6.0) + 1))
    return (32600 if lat >= 0 else 32700) + zone


def local_crs_for(bbox: Bbox, override: str | None = None) -> str:
    """Metric CRS to use for work inside ``bbox``: ``override`` if given, else its UTM zone.

    Raises ValueError if ``override`` is not a CRS pyproj understands.
    """
    if override is not None:
        try:
            pyproj.CRS.from_user_input(override)
        except pyproj.exceptions.CRSError as exc:
            raise ValueError(f"Invalid CRS override {override!r}: {exc}") from exc
        return override
    return f"EPSG:{utm_epsg(*bbox.center())}"


@functools.cache
def transformer(src: str, dst: str) -> pyproj.Transformer:
    """Cached transformer with (lon, lat) / (x, y) axis order."""
    return pyproj.Transformer.from_crs(src, dst, always_xy=True)


def to_local(
    lons: Sequence[float], lats: Sequence[float], crs: str
) -> tuple[list[float], list[float]]:
    """Transform WGS84 lon/lat sequences to ``crs`` x/y lists."""
    xs, ys = transformer(WGS84, crs).transform(list(lons), list(lats))
    return [float(x) for x in xs], [float(y) for y in ys]


def to_wgs84(xs: Sequence[float], ys: Sequence[float], crs: str) -> tuple[list[float], list[float]]:
    """Transform ``crs`` x/y sequences to WGS84 lon/lat lists."""
    lons, lats = transformer(crs, WGS84).transform(list(xs), list(ys))
    return [float(v) for v in lons], [float(v) for v in lats]
