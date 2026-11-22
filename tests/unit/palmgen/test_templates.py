from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from markupsafe import Markup

from palmgen import ids
from palmgen.errors import GenerationError
from palmgen.templates import FormatSpec, TemplateSet, check_template_source

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "palmgen" / "templates"

HEADER = "{# FAKE #}\n"


@pytest.fixture
def ts() -> TemplateSet:
    return TemplateSet.load(FIXTURE)


def make_set(tmp_path: Path, **files: str) -> Path:
    """Copy the fixture set to ``tmp_path`` and replace the given template files."""
    dest = tmp_path / "templates"
    shutil.copytree(FIXTURE, dest)
    for name, text in files.items():
        (dest / name).write_text(text, encoding="utf-8", newline="\n")
    return dest


def set_yaml(dest: Path, old: str, new: str) -> None:
    path = dest / "templates.yaml"
    text = path.read_text(encoding="utf-8")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def test_load_fixture(ts: TemplateSet) -> None:
    assert isinstance(ts.format, FormatSpec)
    assert ts.format.guid_style == "braces_upper"
    assert ts.format.lat_decimals == 8
    assert ts.format.heading_decimals == 3
    assert ts.format.ring_closed is False
    assert ts.names == ("exclusion_polygon", "scene_file", "scenery_object")
    assert ts.count_xpath("scene_file") is None
    assert ts.count_xpath("scenery_object") == "/FixtureScene/FixtureObject"
    assert ts.placeholder_model == {"name": "", "model_guid": "", "native_height_m": None}


def test_missing_value_raises_never_renders_empty(ts: TemplateSet) -> None:
    with pytest.raises(GenerationError, match=r"scenery_object.*'lat' is undefined"):
        ts.render(
            "scenery_object",
            "item",
            name="n",
            self_guid=uuid.UUID(int=1),
            lon="0",
            heading="0",
            scale="1",
            model_guid="m",
        )


def test_missing_self_guid_raises(ts: TemplateSet) -> None:
    with pytest.raises(GenerationError, match="self_guid"):
        ts.render("scene_file", "item", name="n", body=Markup(""))


def test_unknown_template_raises(ts: TemplateSet) -> None:
    with pytest.raises(GenerationError, match="unknown template"):
        ts.render("nope", "item")


def test_guid_roles(ts: TemplateSet) -> None:
    out = ts.render(
        "exclusion_polygon", "poly-1", name="poly-1", self_guid=uuid.UUID(int=0xABC), vertices=[]
    )
    own = ids.format_guid(uuid.UUID(int=0xABC), "braces_upper")
    child = ids.format_guid(ids.child_guid("poly-1", "extra"), "braces_upper")
    assert f'id="{own}"' in out
    assert f'extra="{child}"' in out


@pytest.mark.parametrize("style", ["braces_upper", "braces_lower", "plain_upper", "plain_lower"])
def test_guid_style_is_configurable(tmp_path: Path, style: str) -> None:
    dest = make_set(tmp_path)
    set_yaml(dest, "guid_style: braces_upper", f"guid_style: {style}")
    guid = uuid.UUID("00000000-0000-0000-0000-000000000abc")
    out = TemplateSet.load(dest).render(
        "scene_file", "t", name="t", self_guid=guid, body=Markup("")
    )
    assert f'id="{ids.format_guid(guid, style)}"' in out


@pytest.mark.parametrize(
    "source",
    [
        HEADER + "{% if x %}a{% endif %}",
        HEADER + "{% set x = 1 %}",
        HEADER + "{% for v in vertices if v.ok %}{{ v.lat }}{% endfor %}",
        HEADER + "{% for v in vertices|list %}{{ v.lat }}{% endfor %}",
        HEADER + "{% for v in vertices %}{% else %}{% endfor %}",
        HEADER + "{% include 'x' %}",
        HEADER + "{{ name|upper }}",
        HEADER + "{{ name | default('x') }}",
        HEADER + "{{ a + b }}",
        HEADER + "{{ a if b else c }}",
        HEADER + "{{ guid(role) }}",
        HEADER + "{{ name.upper() }}",
        HEADER + "{{ Name }}",
        HEADER + "{{ name",
    ],
)
def test_forbidden_constructs_rejected_by_scan(source: str) -> None:
    with pytest.raises(GenerationError, match="scenery_object"):
        check_template_source(source, "scenery_object")


@pytest.mark.parametrize(
    "source",
    [
        "{# c #}{{ name }}",
        "{{ guid(\"self\") }}{{ guid( 'a.b-c' ) }}",
        "{% for v in vertices %}{{ v.lat }}{% endfor %}",
        "{%- for v in vertices -%}{{ v.lat }}{%- endfor -%}",
        "{# a | b {% if %} #}text",
    ],
)
def test_allowed_constructs_pass_scan(source: str) -> None:
    check_template_source(source, "t")


def test_conditional_template_rejected_at_load(tmp_path: Path) -> None:
    dest = make_set(tmp_path, **{"scenery_object.xml.j2": "{% if lat %}<A/>{% endif %}\n"})
    with pytest.raises(GenerationError, match=r"scenery_object.*line 1.*only 'for'"):
        TemplateSet.load(dest)


def test_filter_template_rejected_at_load(tmp_path: Path) -> None:
    dest = make_set(tmp_path, **{"scenery_object.xml.j2": '<A x="{{ lat|round }}"/>\n'})
    with pytest.raises(GenerationError, match="filters are not allowed"):
        TemplateSet.load(dest)


def test_syntax_error_rejected_at_load(tmp_path: Path) -> None:
    # The tags look fine to the scan, but Jinja cannot compile an unmatched endfor.
    dest = make_set(tmp_path, **{"scenery_object.xml.j2": "{% endfor %}\n"})
    with pytest.raises(GenerationError, match="scenery_object"):
        TemplateSet.load(dest)


def test_unbalanced_for_rejected_at_load(tmp_path: Path) -> None:
    dest = make_set(tmp_path, **{"scenery_object.xml.j2": "{% for v in vertices %}<A/>\n"})
    with pytest.raises(GenerationError, match="scenery_object"):
        TemplateSet.load(dest)


def test_missing_file_rejected(tmp_path: Path) -> None:
    dest = make_set(tmp_path)
    (dest / "scenery_object.xml.j2").unlink()
    with pytest.raises(GenerationError, match=r"scenery_object.*does not exist"):
        TemplateSet.load(dest)


def test_path_escape_rejected(tmp_path: Path) -> None:
    dest = make_set(tmp_path)
    set_yaml(dest, "scenery_object.xml.j2", "../outside.xml.j2")
    (tmp_path / "outside.xml.j2").write_text("<A/>", encoding="utf-8")
    with pytest.raises(GenerationError, match="outside"):
        TemplateSet.load(dest)


@pytest.mark.parametrize(
    ("old", "new", "match"),
    [
        ("schema_version: 1", "schema_version: 2", "schema_version"),
        ("guid_style: braces_upper", "guid_style: fancy", "guid_style"),
        ("lat_decimals: 8", "lat_decimals: -1", "lat_decimals"),
        ("ring_closed: false", "ring_closed: 0", "ring_closed"),
        ("line_ending: lf", "line_ending: cr", "line_ending"),
        ("vertex_order: ccw", "vertex_order: up", "vertex_order"),
        ("  scale_decimals: 4\n", "", "missing keys: scale_decimals"),
        ("  scene_dir:", "  bogus: 1\n  scene_dir:", "unknown keys: bogus"),
        ('count_xpath: "/FixtureScene/FixtureObject"', 'count_xpath: "//["', "count_xpath"),
    ],
)
def test_bad_templates_yaml_rejected(tmp_path: Path, old: str, new: str, match: str) -> None:
    dest = make_set(tmp_path)
    set_yaml(dest, old, new)
    with pytest.raises(GenerationError, match=match):
        TemplateSet.load(dest)


def test_missing_templates_yaml(tmp_path: Path) -> None:
    with pytest.raises(GenerationError, match="not found"):
        TemplateSet.load(tmp_path)


def test_body_markup_is_not_escaped_but_values_are(ts: TemplateSet) -> None:
    out = ts.render("scene_file", "t", name="a&b", self_guid=uuid.UUID(int=1), body=Markup("<X/>"))
    assert "<X/>" in out
    assert 'name="a&amp;b"' in out
    plain = ts.render("scene_file", "t", name="t", self_guid=uuid.UUID(int=1), body="<X/>")
    assert "&lt;X/&gt;" in plain


def test_crlf_line_ending(tmp_path: Path) -> None:
    dest = make_set(tmp_path)
    set_yaml(dest, "line_ending: lf", "line_ending: crlf")
    out = TemplateSet.load(dest).render(
        "scene_file", "t", name="t", self_guid=uuid.UUID(int=1), body=Markup("")
    )
    assert out.count("\r\n") == out.count("\n") > 0


def test_lf_output_has_no_carriage_returns(ts: TemplateSet) -> None:
    out = ts.render("scene_file", "t", name="t", self_guid=uuid.UUID(int=1), body=Markup(""))
    assert "\r" not in out
    assert out.startswith("<?xml")
    assert out.endswith("</FixtureScene>\n")
