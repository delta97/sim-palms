"""ASSET-006: glTF stats and the automated asset checks."""

import json
import math
import shutil
import struct
import zlib
from pathlib import Path
from typing import Any

import pytest
import yaml

from palmcore.assets.__main__ import main
from palmcore.assets.checks import (
    CheckResult,
    format_results,
    load_budgets,
    run_checks,
)
from palmcore.assets.gltf_stats import GltfError, read_gltf, read_png_size
from palmcore.errors import ConfigError

REPO = Path(__file__).resolve().parents[3]
FIXTURES = REPO / "tests" / "fixtures" / "palmcore" / "assets"
GLTF = FIXTURES / "gltf"
UNIT = GLTF / "unit"
BUDGETS = REPO / "assets" / "budgets.yaml"
SPECIES = "washingtonia_robusta"
NAME = f"palmfix_{SPECIES}_tall"
FRONDS_TEX = f"tx_{SPECIES}_fronds_albedo.png"
BARK_TEX = f"tx_{SPECIES}_bark_albedo.png"
GOOD_TRIS = (4500, 1000, 200, 30)

# --- builders -----------------------------------------------------------------------------


def _acc(
    count: int, lo: list[float] | None = None, hi: list[float] | None = None
) -> dict[str, Any]:
    if lo is None:
        return {"componentType": 5123, "count": count, "type": "SCALAR"}
    return {"componentType": 5126, "count": count, "type": "VEC3", "min": lo, "max": hi}


def _lod_doc(
    *,
    tris: int,
    height: float = 28.0,
    crown: float = 4.5,
    bottom: float = 0.0,
    prims: int = 2,
    materials: list[dict[str, Any]] | None = None,
    images: list[str] | None = None,
) -> dict[str, Any]:
    half = crown / 2
    # Split the triangles across the primitives so the total stays `tris`.
    shares = [tris // prims + (tris % prims if i == 0 else 0) for i in range(prims)]
    primitives = [{"attributes": {"POSITION": i}, "material": min(i, 1)} for i in range(prims)]
    accessors = [_acc(share * 3, [-half, bottom, -half], [half, height, half]) for share in shares]
    mats = (
        [
            {"name": f"mat_{SPECIES}_trunk"},
            {"name": f"mat_{SPECIES}_fronds", "alphaMode": "MASK", "doubleSided": True},
        ]
        if materials is None
        else materials
    )
    uris = images if images is not None else [f"../texture/{FRONDS_TEX}"]
    return {
        "asset": {"version": "2.0"},
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": primitives}],
        "accessors": accessors,
        "materials": mats,
        "images": [{"uri": u} for u in uris],
    }


def _png(path: Path, width: int, height: int) -> None:
    """Signature and IHDR only: enough for the size reader."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    chunk = struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr
    chunk += struct.pack(">I", zlib.crc32(b"IHDR" + ihdr))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk)


def _write(path: Path, doc: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _lib(root: Path) -> Path:
    return root / "PackageSources" / "modelLib" / SPECIES


def _lod_path(root: Path, n: int) -> Path:
    return _lib(root) / NAME / f"{NAME}_LOD{n}.gltf"


def make_assets(
    root: Path,
    *,
    set_: str = "socal",
    status: str = "in_review",
    tris: tuple[int, ...] = GOOD_TRIS,
    tex_size: tuple[int, int] = (1024, 1024),
    height: float = 28.0,
) -> Path:
    """A passing assets tree: one species, one `tall` model with 4 LODs and one texture."""
    spec = {
        "species": SPECIES,
        "common_name": "Mexican fan palm",
        "set": set_,
        "status": status,
        "variants": [{"variant": "tall", "native_height_m": 28.0, "crown_diam_m": 4.5}],
    }
    (root / "species").mkdir(parents=True, exist_ok=True)
    (root / "species" / f"{SPECIES}.yaml").write_text(yaml.safe_dump(spec), encoding="utf-8")
    shutil.copyfile(BUDGETS, root / "budgets.yaml")
    for n, count in enumerate(tris):
        _write(_lod_path(root, n), _lod_doc(tris=count, height=height, prims=1 if n == 3 else 2))
    _png(_lib(root) / "texture" / FRONDS_TEX, *tex_size)
    return root


def _edit_budgets(root: Path, **changes: Any) -> None:
    data = yaml.safe_load((root / "budgets.yaml").read_text(encoding="utf-8"))
    data.update(changes)
    (root / "budgets.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def _rewrite_lod(root: Path, n: int, **kwargs: Any) -> None:
    _write(_lod_path(root, n), _lod_doc(**kwargs))


def _find(results: list[CheckResult], check: str, level: str | None = None) -> list[CheckResult]:
    return [r for r in results if r.check == check and (level is None or r.level == level)]


# --- gltf stats ---------------------------------------------------------------------------


def test_triangles_indexed_non_indexed_and_strip() -> None:
    assert read_gltf(UNIT / "indexed.gltf").triangles == 4  # 12 indices
    assert read_gltf(UNIT / "non_indexed.gltf").triangles == 3  # 9 positions
    assert read_gltf(UNIT / "strip.gltf").triangles == 4  # 6 indices - 2


def test_triangles_fan_and_unsupported_mode(tmp_path: Path) -> None:
    doc = _lod_doc(tris=1, prims=1)
    doc["accessors"].append(_acc(7))
    doc["meshes"][0]["primitives"] = [
        {"attributes": {"POSITION": 0}, "indices": 1, "mode": 6},
        {"attributes": {"POSITION": 0}, "indices": 1, "mode": 1},
    ]
    stats = read_gltf(_write(tmp_path / "m.gltf", doc))
    assert stats.triangles == 5  # fan: 7 - 2; lines: 0
    assert stats.primitives == 2
    assert any("mode 1" in w for w in stats.warnings)


def test_bbox_through_nested_translation_and_scale() -> None:
    stats = read_gltf(UNIT / "nested.gltf")
    assert stats.bbox_min == pytest.approx((-1, 4, 1))
    assert stats.bbox_max == pytest.approx((3, 10, 5))


def test_bbox_through_matrix_node(tmp_path: Path) -> None:
    doc = _lod_doc(tris=1, height=2.0, crown=2.0)
    # Column-major: scale 3 on every axis, translation (0, 5, 0).
    doc["nodes"] = [{"mesh": 0, "matrix": [3, 0, 0, 0, 0, 3, 0, 0, 0, 0, 3, 0, 0, 5, 0, 1]}]
    stats = read_gltf(_write(tmp_path / "m.gltf", doc))
    assert stats.bbox_min == pytest.approx((-3, 5, -3))
    assert stats.bbox_max == pytest.approx((3, 11, 3))


def test_bbox_corners_are_all_transformed(tmp_path: Path) -> None:
    """A 90 degree turn about Z maps the y range 0..4 onto x -4..0."""
    doc = _lod_doc(tris=1, height=4.0, crown=2.0)
    s = math.sqrt(0.5)
    doc["nodes"] = [{"mesh": 0, "rotation": [0, 0, s, s]}]
    stats = read_gltf(_write(tmp_path / "m.gltf", doc))
    assert stats.bbox_min == pytest.approx((-4, -1, -1))
    assert stats.bbox_max == pytest.approx((0, 1, 1))


def test_instanced_mesh_counts_twice(tmp_path: Path) -> None:
    doc = _lod_doc(tris=10, prims=1)
    doc["nodes"] = [{"mesh": 0}, {"mesh": 0, "translation": [10, 0, 0]}]
    doc["scenes"] = [{"nodes": [0, 1]}]
    stats = read_gltf(_write(tmp_path / "m.gltf", doc))
    assert (stats.triangles, stats.primitives) == (20, 2)
    assert stats.bbox_max is not None
    assert stats.bbox_max[0] == pytest.approx(12.25)


def test_materials_and_image_uris() -> None:
    (mat,) = read_gltf(UNIT / "blend.gltf").materials
    assert (mat.name, mat.alpha_mode, mat.double_sided) == (
        "mat_washingtonia_robusta_fronds",
        "BLEND",
        False,
    )
    model = "palmfix_washingtonia_robusta_short"
    lod = read_gltf(GLTF / "PackageSources" / "modelLib" / SPECIES / model / f"{model}_LOD0.gltf")
    assert lod.image_uris == ("../texture/tx_washingtonia_robusta_fronds_albedo.png",)


def test_percent_encoded_uri_is_decoded(tmp_path: Path) -> None:
    doc = _lod_doc(tris=1, images=["../texture/a%20b.png"])
    assert read_gltf(_write(tmp_path / "m.gltf", doc)).image_uris == ("../texture/a b.png",)


def test_glb_is_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "x.glb"
    path.write_bytes(b"glTF")
    with pytest.raises(GltfError, match=r"\.glb is not supported"):
        read_gltf(path)


def test_position_without_min_max_is_an_error(tmp_path: Path) -> None:
    doc = _lod_doc(tris=1)
    del doc["accessors"][0]["min"]
    with pytest.raises(GltfError, match="min/max"):
        read_gltf(_write(tmp_path / "m.gltf", doc))


def test_bad_json_and_cycles_are_errors(tmp_path: Path) -> None:
    bad = tmp_path / "bad.gltf"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(GltfError, match="not valid"):
        read_gltf(bad)
    doc = _lod_doc(tris=1)
    doc["nodes"] = [{"children": [1]}, {"children": [0], "mesh": 0}]
    with pytest.raises(GltfError, match="cycle"):
        read_gltf(_write(tmp_path / "c.gltf", doc))


def test_png_size_parsing(tmp_path: Path) -> None:
    assert read_png_size(UNIT / "png_2x2.png") == (2, 2)
    assert read_png_size(UNIT / "png_3x2.png") == (3, 2)
    _png(tmp_path / "wide.png", 2048, 1024)
    assert read_png_size(tmp_path / "wide.png") == (2048, 1024)
    (tmp_path / "fake.png").write_bytes(b"not a png at all, just text bytes")
    with pytest.raises(GltfError, match="not a PNG"):
        read_png_size(tmp_path / "fake.png")


# --- budgets ------------------------------------------------------------------------------


def test_budgets_file_loads_the_plan_numbers() -> None:
    b = load_budgets(BUDGETS)
    assert b.up_axis == 1
    assert b.lod_triangles == ((3000, 6000), (800, 1500), (150, 300), (0, 50))
    assert b.florida_lod0_max == 3000
    assert (b.max_primitives, b.max_primitives_lod3) == (3, 1)
    assert b.base_range == (-0.25, 0.0)
    assert b.textures["bark_albedo"] == (1024, 2048)


def test_budgets_reject_bad_values(tmp_path: Path) -> None:
    data = yaml.safe_load(BUDGETS.read_text(encoding="utf-8"))
    data["up_axis"] = "w"
    path = tmp_path / "b.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="up_axis"):
        load_budgets(path)


# --- checks: pass and fail ----------------------------------------------------------------


def test_good_tree_has_no_findings(tmp_path: Path) -> None:
    assert run_checks(make_assets(tmp_path)) == []


def test_naming_bad_lod_file_and_extras(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    model = _lod_path(root, 0).parent
    shutil.copyfile(_lod_path(root, 0), model / "tree LOD0.gltf")
    (model / "stray_LOD9.bin").write_bytes(b"")
    (model / "wrong.xml").write_text("<x/>", encoding="utf-8")
    subjects = {r.subject for r in _find(run_checks(root), "Naming", "ERROR")}
    assert {"tree LOD0.gltf", "stray_LOD9.bin", "wrong.xml"} <= subjects


def test_naming_bad_material_name(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    _rewrite_lod(root, 3, tris=30, prims=1, materials=[{"name": "Material.001"}])
    found = _find(run_checks(root), "Naming", "ERROR")
    assert any("Material.001" in r.message for r in found)


def test_naming_bad_texture_name(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    _png(_lib(root) / "texture" / "fronds.png", 512, 512)
    _rewrite_lod(root, 0, tris=4500, images=["../texture/fronds.png"])
    found = _find(run_checks(root), "Naming", "ERROR")
    assert [r.subject for r in found] == ["fronds.png"]


def test_naming_stray_model_folder_warns(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    (_lib(root) / "palmfix_other_thing").mkdir()
    found = _find(run_checks(root), "Naming", "WARN")
    assert [r.subject for r in found] == ["palmfix_other_thing"]


@pytest.mark.parametrize("missing", [1, 3])
def test_lod_count_missing_file(tmp_path: Path, missing: int) -> None:
    root = make_assets(tmp_path)
    _lod_path(root, missing).unlink()
    found = _find(run_checks(root), "LOD count", "ERROR")
    assert len(found) == 1
    assert f"missing LOD{missing}" in found[0].message


def test_lod_count_extra_file(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    shutil.copyfile(_lod_path(root, 3), _lod_path(root, 3).with_name(f"{NAME}_LOD4.gltf"))
    found = _find(run_checks(root), "LOD count", "ERROR")
    assert "extra LOD4" in found[0].message


def test_lod_count_missing_model_folder(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    shutil.rmtree(_lod_path(root, 0).parent)
    assert len(_find(run_checks(root), "LOD count", "ERROR")) == 1
    # A draft species with no model yet is not an error.
    draft = make_assets(tmp_path / "d", status="draft")
    shutil.rmtree(_lod_path(draft, 0).parent)
    assert run_checks(draft) == []


def test_triangle_budget_over_max_is_error(tmp_path: Path) -> None:
    root = make_assets(tmp_path, tris=(6001, 1000, 200, 30))
    found = _find(run_checks(root), "Triangle budget")
    assert [(r.level, r.subject) for r in found] == [("ERROR", f"{NAME}_LOD0.gltf")]


def test_triangle_budget_under_min_is_warn(tmp_path: Path) -> None:
    root = make_assets(tmp_path, tris=(4500, 799, 200, 30))
    found = _find(run_checks(root), "Triangle budget")
    assert [(r.level, r.subject) for r in found] == [("WARN", f"{NAME}_LOD1.gltf")]


def test_triangle_budget_at_the_limits_passes(tmp_path: Path) -> None:
    assert run_checks(make_assets(tmp_path, tris=(6000, 1500, 300, 50))) == []


def test_florida_lod0_has_a_lower_max(tmp_path: Path) -> None:
    over = make_assets(tmp_path, set_="florida", tex_size=(512, 512), tris=(3001, 1000, 200, 30))
    found = _find(run_checks(over), "Triangle budget", "ERROR")
    assert len(found) == 1
    assert "max 3000" in found[0].message
    ok = make_assets(
        tmp_path / "ok", set_="florida", tex_size=(512, 512), tris=(3000, 1000, 200, 30)
    )
    assert _find(run_checks(ok), "Triangle budget") == []


def test_monotonic_triangles(tmp_path: Path) -> None:
    root = make_assets(tmp_path, tris=(4500, 1000, 300, 300))  # LOD2 == LOD3, both in budget
    assert len(_find(run_checks(root), "Monotonic", "ERROR")) == 1


def test_primitives_warn_over_limit(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    _rewrite_lod(root, 0, tris=4500, prims=4)
    _rewrite_lod(root, 3, tris=30, prims=2)
    found = _find(run_checks(root), "Primitives", "WARN")
    assert sorted(r.subject for r in found) == [f"{NAME}_LOD0.gltf", f"{NAME}_LOD3.gltf"]


def test_height_lod0_vs_spec(tmp_path: Path) -> None:
    root = make_assets(tmp_path, height=28.7)  # +2.5 percent on every LOD
    found = _find(run_checks(root), "Height", "ERROR")
    assert [r.subject for r in found] == [f"{NAME}_LOD0.gltf"]
    assert _find(run_checks(make_assets(tmp_path / "ok", height=28.5)), "Height") == []


def test_height_lod_vs_lod0_size_pop(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    _rewrite_lod(root, 2, tris=200, height=26.0)
    found = _find(run_checks(root), "Height", "ERROR")
    assert [r.subject for r in found] == [f"{NAME}_LOD2.gltf"]


def test_base_bottom_out_of_range(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    _rewrite_lod(root, 1, tris=1000, bottom=0.3)
    _rewrite_lod(root, 2, tris=200, bottom=-0.5)
    found = _find(run_checks(root), "Base", "ERROR")
    assert sorted(r.subject for r in found) == [f"{NAME}_LOD1.gltf", f"{NAME}_LOD2.gltf"]
    _rewrite_lod(root, 1, tris=1000, bottom=-0.25)  # on the edge passes
    _rewrite_lod(root, 2, tris=200, bottom=-0.1)
    assert _find(run_checks(root), "Base") == []


def test_crown_extent_warns(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    _rewrite_lod(root, 0, tris=4500, crown=6.0)
    found = _find(run_checks(root), "Crown")
    assert [(r.level, r.subject) for r in found] == [("WARN", f"{NAME}_LOD0.gltf")]


def test_alpha_blend_is_an_error(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    mats = [{"name": f"mat_{SPECIES}_trunk", "alphaMode": "BLEND"}]
    _rewrite_lod(root, 3, tris=30, prims=1, materials=mats)
    found = _find(run_checks(root), "Alpha mode", "ERROR")
    assert any("BLEND" in r.message for r in found)


@pytest.mark.parametrize("part", ["fronds", "skirt", "cards"])
def test_alpha_masked_parts_need_mask_and_double_sided(tmp_path: Path, part: str) -> None:
    root = make_assets(tmp_path)
    name = f"mat_{SPECIES}_{part}"
    _rewrite_lod(root, 0, tris=4500, materials=[{"name": name, "doubleSided": True}])
    found = _find(run_checks(root), "Alpha mode", "ERROR")
    assert [r.message for r in found] == [f"material '{name}' must be MASK, is OPAQUE"]
    _rewrite_lod(root, 0, tris=4500, materials=[{"name": name, "alphaMode": "MASK"}])
    found = _find(run_checks(root), "Alpha mode", "ERROR")
    assert [r.message for r in found] == [f"material '{name}' must be doubleSided"]


def test_textures_not_power_of_two(tmp_path: Path) -> None:
    found = _find(run_checks(make_assets(tmp_path, tex_size=(1000, 1024))), "Textures", "ERROR")
    assert len(found) == 1 and "power-of-two" in found[0].message


def test_textures_over_max_size(tmp_path: Path) -> None:
    found = _find(run_checks(make_assets(tmp_path, tex_size=(4096, 4096))), "Textures", "ERROR")
    assert len(found) == 1 and "exceeds max 2048x2048" in found[0].message
    assert run_checks(make_assets(tmp_path / "ok", tex_size=(2048, 2048))) == []


def test_textures_bark_allows_tall_but_not_wide(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    bark = _lib(root) / "texture" / BARK_TEX
    _png(bark, 1024, 2048)
    both = [f"../texture/{FRONDS_TEX}", f"../texture/{BARK_TEX}"]
    _rewrite_lod(root, 0, tris=4500, images=both)
    assert run_checks(root) == []
    _png(bark, 2048, 1024)
    assert len(_find(run_checks(root), "Textures", "ERROR")) == 1


def test_textures_florida_halves_the_limits(tmp_path: Path) -> None:
    root = make_assets(tmp_path, set_="florida", tex_size=(2048, 2048))
    found = _find(run_checks(root), "Textures", "ERROR")
    assert len(found) == 1 and "exceeds max 1024x1024" in found[0].message


def test_textures_missing_file_and_not_png(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    tex = _lib(root) / "texture" / FRONDS_TEX
    tex.unlink()
    found = _find(run_checks(root), "Textures", "ERROR")
    assert len(found) == 1 and "does not exist" in found[0].message
    tex.write_bytes(b"GIF89a is not a PNG, honest, padding padding")
    found = _find(run_checks(root), "Textures", "ERROR")
    assert len(found) == 1 and "not a PNG" in found[0].message


def test_textures_unreferenced_file_warns(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    _png(_lib(root) / "texture" / BARK_TEX, 1024, 2048)
    found = _find(run_checks(root), "Textures")
    assert [(r.level, r.subject) for r in found] == [("WARN", BARK_TEX)]


def test_unreadable_gltf_is_reported_not_raised(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    _lod_path(root, 2).write_text("{", encoding="utf-8")
    assert len(_find(run_checks(root), "glTF", "ERROR")) == 1


def test_glb_is_flagged(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    _lod_path(root, 0).with_suffix(".glb").write_bytes(b"glTF")
    assert any(".glb" in r.message for r in _find(run_checks(root), "glTF", "ERROR"))


def test_species_filter(tmp_path: Path) -> None:
    root = make_assets(tmp_path, tris=(9000, 1000, 200, 30))
    assert len(_find(run_checks(root, SPECIES), "Triangle budget")) == 1
    with pytest.raises(ConfigError, match="unknown species"):
        run_checks(root, "phoenix_canariensis")


# --- thresholds live only in budgets.yaml -------------------------------------------------


def test_changing_budgets_changes_the_result(tmp_path: Path) -> None:
    root = make_assets(tmp_path)  # LOD0 has 4500 triangles
    assert run_checks(root) == []
    _edit_budgets(
        root,
        lod_triangles={
            0: {"min": 1000, "max": 4000},
            1: {"min": 800, "max": 1500},
            2: {"min": 150, "max": 300},
            3: {"min": 0, "max": 50},
        },
    )
    assert [r.check for r in run_checks(root)] == ["Triangle budget"]
    _edit_budgets(root, base_z_range=[0.1, 0.2])
    assert "Base" in {r.check for r in run_checks(root)}
    _edit_budgets(root, up_axis="z")
    assert "Height" in {r.check for r in run_checks(root)}


# --- CLI ----------------------------------------------------------------------------------


def test_cli_ok_exit_zero_and_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_assets(tmp_path)
    assert main(["check", "--assets-dir", str(root)]) == 0
    assert capsys.readouterr().out.strip() == "0 errors, 0 warnings"


def test_cli_errors_exit_one_with_aligned_table(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_assets(tmp_path, tris=(9000, 799, 200, 30))
    assert main(["check", "--assets-dir", str(root), "--species", SPECIES]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("LEVEL")
    assert lines[-1] == "1 errors, 1 warnings"
    assert len({line.index("Triangle budget") for line in lines[1:-1]}) == 1


def test_cli_warnings_only_exit_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = make_assets(tmp_path, tris=(4500, 799, 200, 30))
    assert main(["check", "--assets-dir", str(root)]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "0 errors, 1 warnings"


def test_cli_usage_errors_exit_two(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    assert main(["check", "--assets-dir", str(root), "--species", "nope_nope"]) == 2
    assert main(["check", "--assets-dir", str(root), "--budgets", str(tmp_path / "x.yaml")]) == 2


def test_cli_on_the_fixture_dir_fails() -> None:
    assert main(["check", "--assets-dir", str(GLTF)]) == 1  # the fixture tree has bad cases


def test_format_results_empty_and_populated() -> None:
    assert format_results([]) == ["0 errors, 0 warnings"]
    rows = [
        CheckResult("ERROR", "Base", "a.gltf", "bad"),
        CheckResult("WARN", "Crown", "bb.gltf", "x"),
    ]
    lines = format_results(rows)
    assert lines[-1] == "1 errors, 1 warnings"
    assert len(lines) == 4


# --- build-manifest uses the measurements -------------------------------------------------


def test_build_manifest_fills_measured_fields(tmp_path: Path) -> None:
    root = make_assets(tmp_path, height=28.3, tris=(4321, 1111, 222, 33))
    shutil.copyfile(FIXTURES / "manifest" / "library.yaml", root / "library.yaml")
    out = tmp_path / "manifest.json"
    assert main(["build-manifest", "--assets-dir", str(root), "--out", str(out)]) == 0
    manifest = json.loads(out.read_text(encoding="utf-8"))
    (variant,) = manifest["species"][SPECIES]["variants"]
    assert variant["native_height_m"] == 28.3
    assert variant["crown_diam_m"] == 4.5
    assert [lod["triangles"] for lod in variant["lods"]] == [4321, 1111, 222, 33]


def test_build_manifest_without_gltf_keeps_yaml_targets(tmp_path: Path) -> None:
    root = make_assets(tmp_path)
    shutil.rmtree(_lod_path(root, 0).parent)
    shutil.copyfile(FIXTURES / "manifest" / "library.yaml", root / "library.yaml")
    out = tmp_path / "manifest.json"
    assert main(["build-manifest", "--assets-dir", str(root), "--out", str(out)]) == 0
    manifest = json.loads(out.read_text(encoding="utf-8"))
    (variant,) = manifest["species"][SPECIES]["variants"]
    assert variant["native_height_m"] == 28
    assert [lod["triangles"] for lod in variant["lods"]] == [None] * 4
