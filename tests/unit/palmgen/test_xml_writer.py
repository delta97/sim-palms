from __future__ import annotations

import dataclasses
import os
import shutil
import uuid
from pathlib import Path

import pytest

from palmgen import ids
from palmgen.errors import GenerationError
from palmgen.model import ExclusionPolygon, Placement, TileContent
from palmgen.templates import TemplateSet
from palmgen.xml_writer import (
    count_elements,
    format_fixed,
    format_heading,
    render_tile,
    write_if_changed,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "palmgen" / "templates"
REGION = "fixture-region"
TILE = "n32p78_w117p26"
RING = ((-117.2601, 32.7801), (-117.2599, 32.7801), (-117.2599, 32.7803))


@pytest.fixture
def ts() -> TemplateSet:
    return TemplateSet.load(FIXTURE)


def polygon(members: tuple[str, ...], ring: tuple[tuple[float, float], ...]) -> ExclusionPolygon:
    return ExclusionPolygon(
        name=ids.polygon_name(REGION, TILE, members),
        member_ids=members,
        part=0,
        ring=ring,
        tile_id=TILE,
        guid=ids.polygon_guid(REGION, TILE, members),
    )


def placement(
    palm_id: str, heading: float = 10.0, lon: float = -117.2555, lat: float = 32.7855
) -> Placement:
    return Placement(
        palm_id=palm_id,
        lon=lon,
        lat=lat,
        tile_id=TILE,
        species="phoenix_canariensis",
        variant="tall",
        model_guid="{FAKE-MODEL}",
        simobject_title=None,
        scale=1.0,
        heading_deg=heading,
        guid=ids.object_guid(REGION, TILE, palm_id),
    )


def tile(polys: list[ExclusionPolygon], objs: list[Placement]) -> TileContent:
    return TileContent(tile_id=TILE, polygons=polys, placements=objs)


def copy_set(tmp_path: Path, **files: str) -> TemplateSet:
    dest = tmp_path / "t"
    shutil.copytree(FIXTURE, dest)
    for name, text in files.items():
        (dest / name).write_text(text, encoding="utf-8", newline="\n")
    return TemplateSet.load(dest)


def test_format_fixed_normalises_negative_zero() -> None:
    assert format_fixed(-0.0, 0) == "0"
    assert format_fixed(-0.0, 3) == "0.000"
    assert format_fixed(-0.0000001, 3) == "0.000"
    assert format_fixed(-0.5, 3) == "-0.500"
    assert format_fixed(32.78, 8) == "32.78000000"
    assert format_fixed(-117.26, 8) == "-117.26000000"


def test_format_fixed_rejects_non_finite() -> None:
    for bad in (float("nan"), float("inf")):
        with pytest.raises(GenerationError):
            format_fixed(bad, 3)


def test_heading_wraps_into_zero_to_360() -> None:
    assert format_heading(360.0, 3) == "0.000"
    assert format_heading(0.0, 3) == "0.000"
    assert format_heading(-0.0, 3) == "0.000"
    assert format_heading(-90.0, 3) == "270.000"
    assert format_heading(720.5, 3) == "0.500"
    assert format_heading(359.9996, 3) == "0.000"
    assert format_heading(-1e-20, 3) == "0.000"
    assert format_heading(359.5, 3) == "359.500"
    assert format_heading(360.0, 0) == "0"


def test_render_tile_counts_match_inputs(ts: TemplateSet) -> None:
    t = tile(
        [polygon(("a",), RING), polygon(("b", "c"), RING)],
        [placement("palm-3"), placement("palm-1"), placement("palm-2")],
    )
    text = render_tile(ts, REGION, t)
    assert count_elements(text, ts.count_xpath("exclusion_polygon") or "") == 2
    assert count_elements(text, ts.count_xpath("scenery_object") or "") == 3
    assert count_elements(text, "//FixtureVertex") == 6


def test_render_tile_empty(ts: TemplateSet) -> None:
    text = render_tile(ts, REGION, tile([], []))
    assert count_elements(text, "/FixtureScene/*") == 0


def test_render_tile_is_sorted_and_deterministic(ts: TemplateSet) -> None:
    polys = [polygon(("b",), RING), polygon(("a",), RING)]
    objs = [placement("palm-2"), placement("palm-1")]
    first = render_tile(ts, REGION, tile(polys, objs))
    second = render_tile(ts, REGION, tile(list(reversed(polys)), list(reversed(objs))))
    assert first == second
    assert first.index(f"excl/{REGION}/{TILE}/a#") < first.index(f"excl/{REGION}/{TILE}/b#")
    assert first.index("palm-1") < first.index("palm-2")
    assert first.index("FixturePolygon") < first.index("FixtureObject")


def test_render_tile_exact_bytes(ts: TemplateSet) -> None:
    obj = placement("palm-1", heading=360.0, lon=-0.0, lat=32.5)
    text = render_tile(ts, REGION, tile([], [obj]))
    name = ids.object_name(REGION, TILE, "palm-1")
    own = ids.format_guid(obj.guid, "braces_upper")
    tile_name = f"gen/{ids.GUID_SCHEME}/tile/{REGION}/{TILE}"
    tile_guid = ids.format_guid(ids.tile_guid(REGION, TILE), "braces_upper")
    assert text == (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<FixtureScene name="{tile_name}" id="{tile_guid}">\n'
        f'<FixtureObject name="{name}" id="{own}" lat="32.50000000" lon="0.00000000" '
        'heading="0.000" scale="1.0000" model="{FAKE-MODEL}"/>\n'
        "</FixtureScene>\n"
    )


def test_render_tile_vertex_format(ts: TemplateSet) -> None:
    text = render_tile(ts, REGION, tile([polygon(("a",), RING)], []))
    assert '<FixtureVertex lat="32.78010000" lon="-117.26010000"/>' in text


def test_xml_escaping_of_name_with_ampersand(ts: TemplateSet) -> None:
    poly = ExclusionPolygon(
        name="Fish & <Chips>",
        member_ids=("a",),
        part=0,
        ring=RING,
        tile_id=TILE,
        guid=uuid.UUID(int=7),
    )
    text = render_tile(ts, REGION, tile([poly], []))
    assert 'name="Fish &amp; &lt;Chips&gt;"' in text
    assert count_elements(text, "//FixturePolygon[@name='Fish &amp; &lt;Chips&gt;']") == 0
    assert count_elements(text, '//FixturePolygon[@name="Fish & <Chips>"]') == 1


def test_missing_value_in_render_tile_raises(tmp_path: Path) -> None:
    broken = copy_set(
        tmp_path,
        **{"scenery_object.xml.j2": '<FixtureObject name="{{ name }}" x="{{ not_provided }}"/>\n'},
    )
    with pytest.raises(GenerationError, match=r"scenery_object.*not_provided"):
        render_tile(broken, REGION, tile([], [placement("palm-1")]))


def test_malformed_template_caught_by_lxml(tmp_path: Path) -> None:
    broken = copy_set(tmp_path, **{"scenery_object.xml.j2": '<FixtureObject name="{{ name }}">\n'})
    with pytest.raises(GenerationError, match=r"scenery_object.*not well-formed"):
        render_tile(broken, REGION, tile([], [placement("palm-1")]))


def test_malformed_scene_file_names_scene_file(tmp_path: Path) -> None:
    broken = copy_set(tmp_path, **{"scene_file.xml.j2": "<FixtureScene>\n{{ body }}\n"})
    with pytest.raises(GenerationError, match=r"scene_file.*not well-formed"):
        render_tile(broken, REGION, tile([], []))


def test_control_character_in_value_rejected(ts: TemplateSet) -> None:
    bad = dataclasses.replace(placement("palm-1"), model_guid="bad\x01guid")
    with pytest.raises(GenerationError, match="not well-formed"):
        render_tile(ts, REGION, tile([], [bad]))


def test_entities_are_not_resolved() -> None:
    xml = '<!DOCTYPE r [<!ENTITY e "x">]><r><a>&e;</a></r>'
    assert count_elements(xml, "//a") == 1


def test_write_if_changed_keeps_mtime(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "tile.xml"
    assert write_if_changed(path, "<A/>\n") is True
    os.utime(path, (1_000_000_000, 1_000_000_000))
    before = path.stat().st_mtime_ns
    assert write_if_changed(path, "<A/>\n") is False
    assert path.stat().st_mtime_ns == before
    assert write_if_changed(path, "<B/>\n") is True
    assert path.stat().st_mtime_ns != before
    assert path.read_bytes() == b"<B/>\n"
    assert [p.name for p in path.parent.iterdir()] == ["tile.xml"]


def test_write_if_changed_writes_exact_bytes(tmp_path: Path) -> None:
    path = tmp_path / "f.xml"
    write_if_changed(path, "a\r\nb\nü\n")
    assert path.read_bytes() == b"a\r\nb\n\xc3\xbc\n"


def test_write_if_changed_cleans_temp_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "f.xml"

    def boom(src: object, dst: object) -> None:
        raise OSError("nope")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="nope"):
        write_if_changed(path, "x")
    assert list(tmp_path.iterdir()) == []


def test_count_elements_errors() -> None:
    with pytest.raises(GenerationError, match="not well-formed"):
        count_elements("<a>", "//a")
    with pytest.raises(GenerationError, match="invalid XPath"):
        count_elements("<a/>", "//[")
    with pytest.raises(GenerationError, match="must select nodes"):
        count_elements("<a/>", "count(//a)")


def test_count_elements_counts() -> None:
    assert count_elements("<a><b/><b/><c/></a>", "//b") == 2
    assert count_elements("<a><b/><b/><c/></a>", "/a/*") == 3
