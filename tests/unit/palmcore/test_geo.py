from __future__ import annotations

import math

import pytest

from palmcore.geo import (
    Bbox,
    haversine_m,
    local_crs_for,
    meters_per_degree,
    to_local,
    to_wgs84,
    transformer,
    utm_epsg,
)

SD = Bbox(-117.28, 32.70, -117.15, 32.82)


@pytest.mark.parametrize(
    ("lon", "lat", "epsg"),
    [(-117.25, 32.79, 32611), (151.2, -33.9, 32756), (180.0, 0.0, 32660), (-180.0, 10.0, 32601)],
)
def test_utm_epsg(lon: float, lat: float, epsg: int) -> None:
    assert utm_epsg(lon, lat) == epsg


def test_local_crs_for() -> None:
    assert local_crs_for(SD) == "EPSG:32611"
    assert local_crs_for(SD, "EPSG:2230") == "EPSG:2230"
    with pytest.raises(ValueError, match="not-a-crs"):
        local_crs_for(SD, "not-a-crs")


def test_haversine() -> None:
    d = haversine_m(-117.25, 32.79, -117.25, 32.791)
    # Sphere with R = 6371008.8 m: 0.001 deg is 111.195 m (independent of latitude).
    assert d == pytest.approx(111.2, abs=0.2)
    # The ellipsoidal metres-per-degree-of-latitude at 32.79 N gives the 110.9 m figure.
    assert meters_per_degree(32.79)[1] / 1000 == pytest.approx(110.9, abs=0.2)
    assert haversine_m(-117.25, 32.79, -117.0, 33.0) == pytest.approx(
        haversine_m(-117.0, 33.0, -117.25, 32.79)
    )
    assert haversine_m(-117.25, 32.79, -117.25, 32.79) == 0.0
    # One degree of longitude on the equator is about 111.19 km on this sphere.
    assert haversine_m(0, 0, 1, 0) == pytest.approx(111_195, abs=50)


def test_meters_per_degree() -> None:
    lon_m, lat_m = meters_per_degree(0)
    assert lon_m == pytest.approx(111320, abs=5)
    assert lat_m == pytest.approx(110574, abs=5)
    lon60, _ = meters_per_degree(60)
    assert lon60 == pytest.approx(55800, abs=100)


@pytest.mark.parametrize(
    "args",
    [
        (math.nan, 0, 1, 1),
        (0, 0, math.inf, 1),
        (-181, 0, 0, 1),
        (0, -91, 1, 1),
        (0, 0, 181, 1),
        (1, 0, 1, 1),
        (2, 0, 1, 1),
        (0, 1, 1, 1),
        (0, 2, 1, 1),
    ],
)
def test_bbox_rejects_invalid(args: tuple[float, float, float, float]) -> None:
    with pytest.raises(ValueError, match="Bbox"):
        Bbox(*args)


def test_bbox_from_list_and_accessors() -> None:
    b = Bbox.from_list([-117.28, 32.70, -117.15, 32.82])
    assert b == SD
    assert b.to_list() == [-117.28, 32.70, -117.15, 32.82]
    assert b.as_tuple() == (-117.28, 32.70, -117.15, 32.82)
    assert b.center() == pytest.approx((-117.215, 32.76))
    with pytest.raises(ValueError, match="exactly 4"):
        Bbox.from_list([1, 2, 3])


def test_bbox_contains_and_intersects() -> None:
    assert SD.contains(-117.28, 32.70)
    assert SD.contains(-117.2, 32.8)
    assert not SD.contains(-117.0, 32.8)
    touching = Bbox(-117.15, 32.70, -117.0, 32.82)
    assert SD.intersects(touching)
    assert touching.intersects(SD)
    assert not SD.intersects(Bbox(-117.0, 32.9, -116.9, 33.0))


def test_bbox_buffer_and_size() -> None:
    grown = SD.buffer_m(100)
    assert (SD.lon_min - grown.lon_min) * meters_per_degree(32.76)[0] == pytest.approx(100, abs=1)
    assert (grown.lat_max - SD.lat_max) * meters_per_degree(32.76)[1] == pytest.approx(100, abs=1)
    assert grown.width_m() == pytest.approx(SD.width_m() + 200, abs=2)
    assert grown.height_m() == pytest.approx(SD.height_m() + 200, abs=2)
    # 0.12 deg of latitude is about 13.3 km.
    assert SD.height_m() == pytest.approx(13_300, abs=100)
    world = Bbox(-179.999, -89.999, 179.999, 89.999).buffer_m(1_000_000)
    assert world.as_tuple() == (-180.0, -90.0, 180.0, 90.0)


def test_round_trip() -> None:
    lons = [-117.25, -117.2, -117.16]
    lats = [32.71, 32.79, 32.81]
    crs = local_crs_for(SD)
    xs, ys = to_local(lons, lats, crs)
    # San Diego in UTM 11N: easting about 480-490 km, northing about 3.61-3.63 Mm.
    assert 470_000 < xs[0] < 495_000
    assert 3_600_000 < ys[0] < 3_630_000
    lons2, lats2 = to_wgs84(xs, ys, crs)
    assert lons2 == pytest.approx(lons, abs=1e-7)
    assert lats2 == pytest.approx(lats, abs=1e-7)


def test_transformer_cached() -> None:
    assert transformer("EPSG:4326", "EPSG:32611") is transformer("EPSG:4326", "EPSG:32611")
