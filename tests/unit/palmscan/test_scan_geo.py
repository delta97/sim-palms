"""palmscan.geo: local CRS selection and round trips."""

from __future__ import annotations

import numpy as np
import pyproj

from palmcore.geo import Bbox
from palmscan.geo import local_crs, to_local, to_wgs84

SD = [-117.28, 32.70, -117.15, 32.82]


def test_san_diego_is_utm_11n() -> None:
    crs = local_crs(SD)
    assert isinstance(crs, pyproj.CRS)
    assert crs.to_epsg() == 32611
    assert local_crs(Bbox.from_list(SD)).to_epsg() == 32611


def test_southern_hemisphere_and_override() -> None:
    assert local_crs([151.0, -34.0, 151.2, -33.8]).to_epsg() == 32756
    assert local_crs(SD, override="EPSG:2230").to_epsg() == 2230


def test_round_trip_within_one_mm() -> None:
    crs = local_crs(SD)
    lon = np.array([-117.2, -117.25, -117.16])
    lat = np.array([32.75, 32.71, 32.81])
    x, y = to_local(lon, lat, crs)
    assert isinstance(x, np.ndarray)
    lon2, lat2 = to_wgs84(x, y, crs)
    x2, y2 = to_local(lon2, lat2, crs)
    assert np.max(np.abs(x2 - x)) < 1e-3
    assert np.max(np.abs(y2 - y)) < 1e-3
    # the degrees agree to better than a millimetre (1 mm is about 9e-9 deg)
    assert np.max(np.abs(lon2 - lon)) < 1e-8
    assert np.max(np.abs(lat2 - lat)) < 1e-8


def test_scalar_in_scalar_out_and_known_value() -> None:
    x, y = to_local(-117.0, 32.0, "EPSG:32611")  # central meridian of zone 11
    assert isinstance(x, float)
    assert abs(x - 500000.0) < 1e-6
    lon, lat = to_wgs84(x, y, "EPSG:32611")
    assert abs(lon + 117.0) < 1e-9
    assert abs(lat - 32.0) < 1e-9


def test_accepts_crs_object_and_preserves_shape() -> None:
    crs = local_crs(SD)
    x, y = to_local(np.full((2, 3), -117.2), np.full((2, 3), 32.75), crs)
    assert x.shape == (2, 3)
    assert y.shape == (2, 3)
