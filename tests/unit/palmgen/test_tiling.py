from __future__ import annotations

import random

import pytest

from palmcore.geo import Bbox
from palmgen.errors import InputError
from palmgen.model import Palm
from palmgen.tiling import (
    TILE_DEG,
    assign_polygon_tile,
    check_bbox,
    parse_tile_id,
    tile_bounds,
    tile_filename,
    tile_id,
    tile_index,
)

SOCAL = Bbox(-117.28, 32.70, -117.15, 32.82)


def test_tile_deg() -> None:
    assert TILE_DEG == 0.01


def test_plan_example() -> None:
    # Plan example: lon -117.2531, lat 32.7893 -> ix=-11726, iy=3278.
    assert tile_index(-117.2531, 32.7893) == (-11726, 3278)
    assert tile_id(-11726, 3278) == "n32p78_w117p26"
    assert tile_filename("n32p78_w117p26") == "tile_n32p78_w117p26.xml"
    assert tile_bounds("n32p78_w117p26") == (-117.26, 32.78, -117.25, 32.79)


@pytest.mark.parametrize(
    ("lon", "lat", "expected"),
    [
        # Points exactly on a tile edge belong to the tile whose south-west corner they are.
        (-117.26, 32.79, "n32p79_w117p26"),
        (-117.26, 32.78, "n32p78_w117p26"),
        (-117.25, 32.78, "n32p78_w117p25"),
        # Just either side of an edge.
        (-117.2501, 32.7801, "n32p78_w117p26"),
        (-117.2499, 32.7799, "n32p77_w117p25"),
        # Negative latitude: lat -0.005 is south of the 0.00 edge, so its tile is s0p01.
        (-0.005, -0.005, "s0p01_w0p01"),
        (0.005, -0.005, "s0p01_e0p00"),
        (-0.01, -0.01, "s0p01_w0p01"),
        (-0.0100001, -0.0100001, "s0p02_w0p02"),
        # Hemispheres and zero.
        (0.0, 0.0, "n0p00_e0p00"),
        (-0.0, -0.0, "n0p00_e0p00"),
        (0.005, 0.005, "n0p00_e0p00"),
        (-0.005, 0.005, "n0p00_w0p01"),
        (10.5, -10.5, "s10p50_e10p50"),
        # Antimeridian edges: lon 180.0 is the west edge of e180p00; -180.0 is w180p00.
        (180.0, 0.0, "n0p00_e180p00"),
        (179.995, 0.0, "n0p00_e179p99"),
        (-180.0, 0.0, "n0p00_w180p00"),
        (-179.995, 0.0, "n0p00_w180p00"),
        (-179.99, 0.0, "n0p00_w179p99"),
        # Poles.
        (0.0, 90.0, "n90p00_e0p00"),
        (0.0, -90.0, "s90p00_e0p00"),
    ],
)
def test_tile_for_point(lon: float, lat: float, expected: str) -> None:
    ix, iy = tile_index(lon, lat)
    assert tile_id(ix, iy) == expected
    assert parse_tile_id(expected) == (ix, iy)


def test_float_noise_snaps_to_the_intended_edge() -> None:
    # Representation noise far below 1e-8 degree does not move a point off its edge.
    assert tile_index(-117.26000000000001, 32.79) == (-11726, 3279)
    assert tile_index(-117.26, 32.79) == (-11726, 3279)
    # -117.20000000001 is 1e-11 degree west of the -117.20 edge. It snaps onto the edge and so
    # takes w117p20, not w117p21 (the grid resolution is 1e-8 degree; see module docstring).
    assert tile_index(-117.20000000001, 32.79) == tile_index(-117.20, 32.79) == (-11720, 3279)
    # 1e-7 degree west of the edge is above the resolution, so it is in the tile to the west.
    assert tile_index(-117.2000001, 32.79) == (-11721, 3279)


def test_negative_zero_is_the_zero_edge() -> None:
    assert tile_index(-0.0, -0.0) == (0, 0)
    assert tile_id(0, 0) == "n0p00_e0p00"
    assert parse_tile_id("n0p00_e0p00") == (0, 0)
    with pytest.raises(ValueError):
        parse_tile_id("s0p00_e0p00")  # -0 is not a distinct tile
    with pytest.raises(ValueError):
        parse_tile_id("n0p00_w0p00")


def test_non_finite_coordinates_are_rejected() -> None:
    with pytest.raises(ValueError):
        tile_index(float("nan"), 0.0)
    with pytest.raises(ValueError):
        tile_index(0.0, float("inf"))


@pytest.mark.parametrize(
    ("ix", "iy"),
    [(0, 0), (-1, -1), (18000, 9000), (-18000, -9000), (18000, -9000), (-18000, 9000), (1, 0)],
)
def test_round_trip_edge_indices(ix: int, iy: int) -> None:
    assert parse_tile_id(tile_id(ix, iy)) == (ix, iy)


def test_round_trip_random_grid() -> None:
    rng = random.Random(20261122)
    for _ in range(1000):
        ix = rng.randint(-18000, 18000)
        iy = rng.randint(-9000, 9000)
        tid = tile_id(ix, iy)
        assert parse_tile_id(tid) == (ix, iy)
        assert tile_filename(tid) == f"tile_{tid}.xml"


@pytest.mark.parametrize(
    "tid",
    [
        "",
        "n32p78",
        "n32p78_w117p2",  # frac must have 2 digits
        "n32p7_w117p26",
        "N32p78_w117p26",  # case-sensitive
        "n32p78-w117p26",
        "n32p78_w117p26\n",  # no trailing newline
        " n32p78_w117p26",
        "n032p78_w117p26",  # non-canonical leading zero
        "n32p78_w117p026",
        "n91p00_e0p00",  # beyond the poles
        "n32p78_e180p01",  # beyond the antimeridian
        "x32p78_w117p26",
        "n32p78_w117p26_extra",
    ],
)
def test_parse_rejects_bad_ids(tid: str) -> None:
    with pytest.raises(ValueError):
        parse_tile_id(tid)
    with pytest.raises(ValueError):
        tile_filename(tid)


def test_tile_id_rejects_out_of_range_indices() -> None:
    with pytest.raises(ValueError):
        tile_id(18001, 0)
    with pytest.raises(ValueError):
        tile_id(0, -9001)


def test_bounds_contain_their_points() -> None:
    rng = random.Random(7)
    tol = 1e-8
    for _ in range(1000):
        lon = rng.uniform(-117.28, -117.15)
        lat = rng.uniform(32.70, 32.82)
        lon_min, lat_min, lon_max, lat_max = tile_bounds(tile_id(*tile_index(lon, lat)))
        assert lon_min - tol <= lon <= lon_max + tol
        assert lat_min - tol <= lat <= lat_max + tol
        assert lon_max - lon_min == pytest.approx(TILE_DEG)
        assert lat_max - lat_min == pytest.approx(TILE_DEG)


def test_bounds_hemisphere_edges() -> None:
    assert tile_bounds("s0p01_e0p00") == (0.0, -0.01, 0.01, 0.0)
    assert tile_bounds("n0p00_w0p01") == (-0.01, 0.0, 0.0, 0.01)
    assert tile_bounds("n0p00_w180p00") == (-180.0, 0.0, -179.99, 0.01)
    assert tile_bounds("s90p00_e0p00") == (0.0, -90.0, 0.01, -89.99)


def test_polygon_tile_uses_smallest_palm_id() -> None:
    palms = [
        Palm("palm_b", -117.2531, 32.7893, "x", None, None, None, False),
        Palm("palm_a", -117.2701, 32.7902, "x", None, None, None, False),
        Palm("palm_c", -117.2600, 32.7950, "x", None, None, None, False),
    ]
    member_points = {p.palm_id: (p.lon, p.lat) for p in palms}
    # palm_a is the smallest id: -117.2701 -> w117p28, 32.7902 -> n32p79.
    assert assign_polygon_tile(member_points) == "n32p79_w117p28"
    # Dict order does not matter.
    reordered = {k: member_points[k] for k in ("palm_c", "palm_b", "palm_a")}
    assert assign_polygon_tile(reordered) == "n32p79_w117p28"


def test_polygon_tile_single_member() -> None:
    assert assign_polygon_tile({"p1": (-117.25, 32.79)}) == "n32p79_w117p25"


def test_polygon_tile_rejects_empty() -> None:
    with pytest.raises(InputError):
        assign_polygon_tile({})


def test_check_bbox_accepts_valid_boxes() -> None:
    assert check_bbox(SOCAL) == SOCAL
    assert check_bbox([-117.28, 32.70, -117.15, 32.82]) == SOCAL


def test_check_bbox_rejects_antimeridian_crossing() -> None:
    with pytest.raises(InputError, match="antimeridian"):
        check_bbox([170.0, 32.0, -170.0, 33.0])


@pytest.mark.parametrize(
    "values",
    [
        [-117.15, 32.70, -117.28, 32.82],  # reversed lon (not a wrap; still rejected)
        [-117.28, 91.0, -117.15, 92.0],  # latitude out of range
        [-117.28, -91.0, -117.15, 32.82],
        [-181.0, 32.70, -117.15, 32.82],  # longitude out of range
        [-117.28, 32.70, -117.15],  # wrong count
        [-117.28, 32.70, -117.28, 32.82],  # degenerate
        [-117.28, float("nan"), -117.15, 32.82],
    ],
)
def test_check_bbox_rejects_bad_values(values: list[float]) -> None:
    with pytest.raises(InputError):
        check_bbox(values)
