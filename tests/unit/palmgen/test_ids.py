from __future__ import annotations

import subprocess
import sys

import pytest

from palmgen import ids as gen_ids
from palmgen.ids import (
    GUID_SCHEME,
    child_guid,
    format_guid,
    object_guid,
    object_name,
    polygon_guid,
    polygon_name,
    tile_guid,
    unit_hash,
)

REGION = "san-diego"
TILE = "n32p79_w117p26"
PALM = "sdc-a6924214cef25e3a"

# Golden values. Changing any of them changes every GUID or hash in shipped packages:
# bump GUID_SCHEME (and the MAJOR version) and update these literals in the same change.
GOLDEN_POLYGON_GUID = "1b0896b4-4e27-5e67-8a46-ee1961718a57"  # members sdc-b,sdc-a; part 1
GOLDEN_OBJECT_GUID = "a842b114-291a-508e-b161-c2a7b22dd3d5"
GOLDEN_TILE_GUID = "09de1f73-da8a-531a-b07a-f5812b10a537"
GOLDEN_UNIT_HASH_HEADING = 0.7849566953471325
GOLDEN_UNIT_HASH_ALT = 0.33255646438921027


def test_scheme_is_v1() -> None:
    assert GUID_SCHEME == "v1"


def test_golden_guids_pinned() -> None:
    assert str(polygon_guid(REGION, TILE, ["sdc-b", "sdc-a"], 1)) == GOLDEN_POLYGON_GUID
    assert str(object_guid(REGION, TILE, PALM)) == GOLDEN_OBJECT_GUID
    assert str(tile_guid(REGION, TILE)) == GOLDEN_TILE_GUID


def test_golden_unit_hashes_pinned() -> None:
    assert unit_hash(PALM, "heading") == GOLDEN_UNIT_HASH_HEADING
    assert unit_hash(PALM, "alt") == GOLDEN_UNIT_HASH_ALT


def test_same_inputs_same_guids_in_one_process() -> None:
    assert object_guid(REGION, TILE, PALM) == object_guid(REGION, TILE, PALM)
    assert polygon_guid(REGION, TILE, ["a", "b"]) == polygon_guid(REGION, TILE, ["a", "b"])


def test_same_inputs_same_guids_in_fresh_interpreter() -> None:
    code = (
        "from palmgen.ids import object_guid, polygon_guid, tile_guid, unit_hash\n"
        f"print(object_guid({REGION!r}, {TILE!r}, {PALM!r}))\n"
        f"print(polygon_guid({REGION!r}, {TILE!r}, ['sdc-b', 'sdc-a'], 1))\n"
        f"print(tile_guid({REGION!r}, {TILE!r}))\n"
        f"print(unit_hash({PALM!r}, 'heading'))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )
    assert result.stdout.split() == [
        GOLDEN_OBJECT_GUID,
        GOLDEN_POLYGON_GUID,
        GOLDEN_TILE_GUID,
        repr(GOLDEN_UNIT_HASH_HEADING),
    ]


def test_polygon_member_order_irrelevant() -> None:
    a = polygon_guid(REGION, TILE, ["sdc-c", "sdc-a", "sdc-b"], 0)
    b = polygon_guid(REGION, TILE, ["sdc-b", "sdc-c", "sdc-a"], 0)
    assert a == b
    assert polygon_name(REGION, TILE, ["sdc-c", "sdc-a", "sdc-b"]) == polygon_name(
        REGION, TILE, ["sdc-a", "sdc-b", "sdc-c"]
    )


def test_polygon_name_format_sorts_members() -> None:
    assert (
        polygon_name(REGION, TILE, ["sdc-b", "sdc-a"], 1)
        == f"gen/v1/excl/{REGION}/{TILE}/sdc-a,sdc-b#1"
    )


def test_object_name_format() -> None:
    assert object_name(REGION, TILE, PALM) == f"gen/v1/obj/{REGION}/{TILE}/{PALM}"


@pytest.mark.parametrize("members", [[], ()])
def test_polygon_empty_members_raise(members: list[str]) -> None:
    with pytest.raises(ValueError):
        polygon_name(REGION, TILE, members)
    with pytest.raises(ValueError):
        polygon_guid(REGION, TILE, members)


def test_changing_any_name_part_changes_guid() -> None:
    base = object_guid(REGION, TILE, PALM)
    assert object_guid("other-region", TILE, PALM) != base
    assert object_guid(REGION, "n32p79_w117p27", PALM) != base
    assert object_guid(REGION, TILE, "sdc-a6924214cef25e3b") != base
    assert tile_guid(REGION, TILE) != tile_guid("other-region", TILE)
    assert polygon_guid(REGION, TILE, ["sdc-a"], 0) != polygon_guid(REGION, TILE, ["sdc-a"], 1)
    assert polygon_guid(REGION, TILE, ["sdc-a"], 0) != polygon_guid(REGION, TILE, ["sdc-b"], 0)


def test_kinds_do_not_collide() -> None:
    values = {
        object_guid(REGION, TILE, PALM),
        tile_guid(REGION, TILE),
        polygon_guid(REGION, TILE, [PALM], 0),
    }
    assert len(values) == 3


def test_child_guid_depends_on_parent_and_role() -> None:
    parent = object_name(REGION, TILE, PALM)
    base = child_guid(parent, "self")
    assert child_guid(parent, "self") == base
    assert child_guid(parent, "shadow") != base
    assert child_guid(object_name(REGION, TILE, "sdc-x"), "self") != base


def test_100k_object_guids_are_distinct() -> None:
    values = {object_guid(REGION, TILE, f"sdc-{i:016x}") for i in range(100_000)}
    assert len(values) == 100_000


@pytest.mark.parametrize(
    ("style", "expected"),
    [
        ("braces_upper", "{09DE1F73-DA8A-531A-B07A-F5812B10A537}"),
        ("braces_lower", "{09de1f73-da8a-531a-b07a-f5812b10a537}"),
        ("plain_upper", "09DE1F73-DA8A-531A-B07A-F5812B10A537"),
        ("plain_lower", "09de1f73-da8a-531a-b07a-f5812b10a537"),
    ],
)
def test_format_guid_styles(style: str, expected: str) -> None:
    assert format_guid(tile_guid(REGION, TILE), style) == expected


def test_format_guid_unknown_style_raises() -> None:
    with pytest.raises(ValueError):
        format_guid(tile_guid(REGION, TILE), "bogus")


def test_unit_hash_in_unit_interval() -> None:
    for i in range(10_000):
        value = unit_hash(f"sdc-{i:016x}", "heading")
        assert 0.0 <= value < 1.0


def test_unit_hash_depends_on_purpose_and_palm() -> None:
    assert unit_hash(PALM, "heading") != unit_hash(PALM, "alt")
    assert unit_hash(PALM, "heading") != unit_hash("sdc-x", "heading")


def test_module_reuses_palmcore_namespace() -> None:
    from palmcore.ids import NAMESPACE

    assert gen_ids.core.NAMESPACE == NAMESPACE
