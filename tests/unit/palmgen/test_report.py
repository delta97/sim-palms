from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path

import pytest

from palmgen import report as rpt
from palmgen.model import (
    BuildWarning,
    Check,
    CompileResult,
    ExclusionPolygon,
    GenerateResult,
    Placement,
    TileContent,
)
from palmgen.paths import package_name, project_dir
from palmgen.report import MaskStat, ReportContext, strip_volatile
from tests.helpers.fixtures import fixture_path

REGION = "san-diego-coastal"
EXPECTED_KEYS = [
    "result",
    "region",
    "package_name",
    "version",
    "package_version",
    "generator_version",
    "data_version",
    "placement",
    "models",
    "inputs",
    "counts",
    "masks",
    "variants",
    "tiles",
    "timings",
    "fspackagetool",
    "checks",
    "warnings",
]
PLAN_COUNT_KEYS = [
    "palms_in",
    "dropped_outside_bbox",
    "dropped_by_mask",
    "dropped_in_building",
    "radius_defaulted",
    "radius_clamped",
    "clusters",
    "clusters_split",
    "polygons",
    "polygon_parts_from_clip",
    "objects",
    "scale_clamped",
    "species_fallback",
    "height_missing",
    "tiles",
]


@dataclass(frozen=True)
class FakeVersion:
    package_version: str = "1.3.0"
    generator_version: str = "1.3.0"
    data_version: str = "2026-11"


def _placement(palm_id: str, tile: str, species: str, variant: str, scale: float) -> Placement:
    return Placement(
        palm_id=palm_id,
        lon=-117.2,
        lat=32.7,
        tile_id=tile,
        species=species,
        variant=variant,
        model_guid="{00000000-0000-0000-0000-000000000001}",
        simobject_title=None,
        scale=scale,
        heading_deg=10.0,
        guid=uuid.UUID(int=len(palm_id)),
    )


def _polygon(name: str, tile: str) -> ExclusionPolygon:
    return ExclusionPolygon(
        name=name,
        member_ids=("p1",),
        part=0,
        ring=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 0.0)),
        tile_id=tile,
        guid=uuid.UUID(int=7),
    )


def make_generate(warnings: list[BuildWarning] | None = None) -> GenerateResult:
    """Fixed generation result: two tiles, two species, one warning code twice."""
    tile_b = TileContent(
        tile_id="n32p79_w117p26",
        polygons=[_polygon("poly-b", "n32p79_w117p26")],
        placements=[
            _placement("p2", "n32p79_w117p26", "Washingtonia", "robusta", 1.1),
            _placement("p3", "n32p79_w117p26", "Phoenix", "canariensis", 0.95),
        ],
    )
    tile_a = TileContent(
        tile_id="n32p78_w117p26",
        polygons=[_polygon("poly-a", "n32p78_w117p26")],
        placements=[
            _placement("p1", "n32p78_w117p26", "Washingtonia", "robusta", 0.9),
        ],
    )
    default_warnings = [
        BuildWarning("SCALE_CLAMPED", "p2 scale 1.30 clamped to 1.15", "p2"),
        BuildWarning("RADIUS_DEFAULTED", "p1 has no crown diameter", "p1"),
        BuildWarning("SCALE_CLAMPED", "p3 scale 0.80 clamped to 0.85", "p3"),
    ]
    return GenerateResult(
        region=REGION,
        package_name=package_name(REGION),
        version=FakeVersion(),
        # Tiles deliberately out of order: the report must sort them.
        tiles=[tile_b, tile_a],
        counts={"palms_in": 3, "polygons": 2, "objects": 3, "tiles": 2, "radius_defaulted": 1},
        warnings=default_warnings if warnings is None else warnings,
        timings={"generate_s": 1.25, "checks_s": 0.5},
    )


def make_compile(exit_code: int = 0, log_path: Path | None = None) -> CompileResult:
    return CompileResult(
        exit_code=exit_code,
        duration_s=12.3456,
        command=[
            "C:/Program Files/fspackagetool/fspackagetool.exe",
            "palmfix-san-diego-coastal.xml",
            "-outputdir",
            "out",
            "-nopause",
        ],
        log_path=log_path if log_path is not None else Path("logs/fspackagetool.log"),
    )


def make_checks(passed: bool = True) -> list[Check]:
    return [
        Check("polygon_count_matches", "2", "2", True),
        Check("exit_code_zero", "0", "0", True),
        Check("bgl_per_tile", "2", "2" if passed else "1", passed),
        Check("object_count_matches", "3", "3", True),
        Check("no_error_lines_in_log", "0", "0", True),
    ]


def make_context() -> ReportContext:
    return ReportContext(
        placement="static",
        models="library",
        inputs={
            "palms": ("build/scan/san-diego-coastal/palms.geojson", "a" * 64),
            "buildings": ("build/scan/san-diego-coastal/buildings.geojson", "b" * 64),
            "manifest": ("assets/manifest.json", "c" * 64),
            "config": ("regions/san-diego-coastal.yaml", "d" * 64),
            "templates": ("palmgen/templates", "e" * 64),
        },
        masks=[
            MaskStat("airport-lindbergh", "airport", palms_dropped=0, polygons_clipped=1),
            MaskStat("park-balboa", "mask", palms_dropped=1, polygons_clipped=0),
        ],
        bgl_by_tile={
            "n32p78_w117p26": "tile_n32p78_w117p26.bgl",
            "n32p79_w117p26": "tile_n32p79_w117p26.bgl",
        },
    )


def make_report(
    *,
    compile_result: CompileResult | None = None,
    checks: list[Check] | None = None,
    generate_timings: dict[str, float] | None = None,
) -> dict:
    gen = make_generate()
    if generate_timings is not None:
        gen.timings = generate_timings
    comp = make_compile() if compile_result is None else compile_result
    return rpt.build_report_dict(
        gen, comp, make_checks() if checks is None else checks, make_context()
    )


def test_top_level_keys_in_plan_order() -> None:
    report = make_report()
    assert list(report) == EXPECTED_KEYS


def test_counts_keys_in_plan_order_and_zero_filled() -> None:
    report = make_report()
    assert list(report["counts"]) == PLAN_COUNT_KEYS
    assert report["counts"]["dropped_by_mask"] == 0
    assert report["counts"]["palms_in"] == 3


def test_identity_fields_and_version_string() -> None:
    report = make_report()
    assert report["region"] == REGION
    assert report["package_name"] == "palmfix-san-diego-coastal"
    assert report["version"] == "1.3.0+data2026-11"
    assert report["placement"] == "static"
    assert report["models"] == "library"


def test_lists_are_sorted_and_aggregated() -> None:
    report = make_report()
    assert [t["tile_id"] for t in report["tiles"]] == ["n32p78_w117p26", "n32p79_w117p26"]
    assert [(v["species"], v["variant"]) for v in report["variants"]] == [
        ("Phoenix", "canariensis"),
        ("Washingtonia", "robusta"),
    ]
    washingtonia = report["variants"][1]
    assert washingtonia["count"] == 2
    assert washingtonia["scale_min"] == 0.9
    assert washingtonia["scale_median"] == 1.0
    assert washingtonia["scale_max"] == 1.1
    assert [m["name"] for m in report["masks"]] == ["airport-lindbergh", "park-balboa"]
    assert [c["name"] for c in report["checks"]] == sorted(c.name for c in make_checks())


def test_warnings_grouped_by_code_with_examples() -> None:
    report = make_report()
    assert report["warnings"] == [
        {
            "code": "RADIUS_DEFAULTED",
            "count": 1,
            "examples": ["p1 has no crown diameter"],
        },
        {
            "code": "SCALE_CLAMPED",
            "count": 2,
            "examples": ["p2 scale 1.30 clamped to 1.15", "p3 scale 0.80 clamped to 0.85"],
        },
    ]


def test_warning_examples_capped_at_twenty() -> None:
    many = [BuildWarning("OUTSIDE_BBOX", f"palm {i} outside", f"p{i}") for i in range(25)]
    gen = make_generate(warnings=many)
    report = rpt.build_report_dict(gen, make_compile(), make_checks(), make_context())
    (entry,) = report["warnings"]
    assert entry["count"] == 25
    assert len(entry["examples"]) == 20
    assert entry["examples"][0] == "palm 0 outside"


@pytest.mark.parametrize(
    ("exit_code", "passed", "expected"),
    [
        (0, True, "PASS"),
        (0, False, "FAIL"),
        (4, True, "FAIL"),
        (4, False, "FAIL"),
    ],
)
def test_result_fail_logic(exit_code: int, passed: bool, expected: str) -> None:
    report = make_report(compile_result=make_compile(exit_code), checks=make_checks(passed))
    assert report["result"] == expected


def test_result_without_compile_depends_on_checks() -> None:
    gen = make_generate()
    assert rpt.build_report_dict(gen, None, make_checks())["result"] == "PASS"
    assert rpt.build_report_dict(gen, None, make_checks(False))["result"] == "FAIL"


def test_skipped_compile_has_empty_tool_section() -> None:
    gen = make_generate()
    report = rpt.build_report_dict(gen, None, make_checks(), make_context())
    assert report["fspackagetool"]["exit_code"] is None
    assert report["fspackagetool"]["command"] == []
    assert report["timings"]["compile_s"] == 0.0


def test_compile_log_lines_are_counted(tmp_path: Path) -> None:
    log = tmp_path / "fspackagetool.log"
    log.write_text(
        "Compiling...\nWarning: texture missing\nERROR: bad XML\nwarning again\nok\n",
        encoding="utf-8",
    )
    report = rpt.build_report_dict(
        make_generate(), make_compile(log_path=log), make_checks(), make_context()
    )
    assert report["fspackagetool"]["warning_lines"] == 2
    assert report["fspackagetool"]["error_lines"] == 1


def test_timings_rounded_and_total_is_sum() -> None:
    report = make_report(generate_timings={"generate_s": 1.25, "checks_s": 0.5})
    assert report["timings"] == {
        "generate_s": 1.25,
        "compile_s": 12.346,
        "checks_s": 0.5,
        "total_s": 14.096,
    }


def test_tile_bgl_null_when_not_known() -> None:
    gen = make_generate()
    report = rpt.build_report_dict(gen, make_compile(), make_checks())
    assert [t["bgl"] for t in report["tiles"]] == [None, None]


def test_strip_volatile_is_stable_across_timings() -> None:
    first = make_report(generate_timings={"generate_s": 1.0, "checks_s": 0.1})
    second = make_report(generate_timings={"generate_s": 9.0, "checks_s": 7.7})
    second["fspackagetool"]["log_path"] = "elsewhere/fspackagetool.log"
    first_stripped = strip_volatile(first)
    second_stripped = strip_volatile(second)
    assert first_stripped == second_stripped
    assert "timings" not in first_stripped
    assert "fspackagetool" not in first_stripped
    assert all("path" not in info for info in first_stripped["inputs"].values())
    assert rpt.report_json_text(first_stripped) == rpt.report_json_text(second_stripped)


def test_strip_volatile_does_not_mutate_input() -> None:
    report = make_report()
    strip_volatile(report)
    assert "timings" in report
    assert "path" in report["inputs"]["palms"]


def test_render_md_matches_snapshot() -> None:
    fixed = make_report()
    expected = fixture_path("palmgen", "report/expected.md").read_bytes().decode("utf-8")
    assert rpt.render_report_md(fixed) == expected


def test_render_md_empty_sections_say_none() -> None:
    gen = make_generate(warnings=[])
    gen.tiles = []
    report = rpt.build_report_dict(gen, None, [], ReportContext())
    text = rpt.render_report_md(report)
    assert text.count("_None._") == 6
    assert "## Warnings\n\n_None._\n" in text


def test_write_reports_writes_utf8_lf_files(tmp_path: Path) -> None:
    out = project_dir(tmp_path, REGION)
    report = make_report()
    rpt.write_reports(out, report)
    json_bytes = (out / "build_report.json").read_bytes()
    md_bytes = (out / "build_report.md").read_bytes()
    assert b"\r" not in json_bytes and b"\r" not in md_bytes
    assert not json_bytes.startswith(b"\xef\xbb\xbf")
    assert json.loads(json_bytes.decode("utf-8"))["region"] == REGION
    assert md_bytes.decode("utf-8") == rpt.render_report_md(report)


def test_write_reports_keeps_mtime_when_unchanged(tmp_path: Path) -> None:
    out = project_dir(tmp_path, REGION)
    report = make_report()
    rpt.write_reports(out, report)
    json_path = out / "build_report.json"
    before = json_path.stat().st_mtime_ns
    rpt.write_reports(out, report)
    assert json_path.stat().st_mtime_ns == before
