"""Self-tests for tests/visual/new_run.py: create, placeholder refusal, finalize, CLI.

Each test works in a temp copy of the visual folder layout and uses generated images, never the
sim. Sites come from a copy of the helpers fixture (one defined site) or a placeholder copy.
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
from pathlib import Path

import pytest
from PIL import Image

from tests.helpers.fixtures import REPO_ROOT, fixture_path
from tests.visual import new_run
from tests.visual.new_run import (
    CHECKLIST,
    PROFILES,
    RUN_YAML,
    TEMPLATE,
    TEST_LOG,
    VisualRunError,
    create_run,
    finalize_run,
    main,
    parse_variants,
    split_row,
    visual_dir,
)

DAY = dt.date(2026, 11, 22)
BASE_NS = 1_700_000_000 * 1_000_000_000
COMMITTED_LOG = REPO_ROOT / "tests" / "visual" / TEST_LOG


@pytest.fixture
def root(tmp_path: Path) -> Path:
    dest = visual_dir(tmp_path)
    dest.mkdir(parents=True)
    for name in (TEMPLATE, PROFILES, TEST_LOG):
        shutil.copy(REPO_ROOT / "tests" / "visual" / name, dest / name)
    return tmp_path


@pytest.fixture
def defined_sites(tmp_path: Path) -> Path:
    path = tmp_path / "sites_defined.yaml"
    shutil.copy(fixture_path("helpers", "sites/valid.yaml"), path)
    return path


@pytest.fixture
def placeholder_sites(tmp_path: Path) -> Path:
    path = tmp_path / "sites_placeholder.yaml"
    text = fixture_path("helpers", "sites/valid.yaml").read_text(encoding="utf-8")
    path.write_text(text.replace("status: defined", "status: placeholder", 1), encoding="utf-8")
    return path


def _create(root: Path, sites: Path, **overrides: object) -> Path:
    options: dict[str, object] = {
        "day": DAY,
        "label": "phase2",
        "sim_version": "1.9.24.0",
        "region_pkg": "0.3.0",
        "root": root,
        "sites_file": sites,
    }
    options.update(overrides)
    return create_run("T1", **options)  # type: ignore[arg-type]


def _log_rows(root: Path) -> list[str]:
    lines = (visual_dir(root) / TEST_LOG).read_text(encoding="utf-8").split("\n")
    return [line for line in lines if line.startswith("| 20")]


def _write_png(path: Path, width: int, height: int, mtime_ns: int) -> None:
    Image.new("RGB", (width, height), (40, 120, 60)).save(path, format="PNG")
    os.utime(path, ns=(mtime_ns, mtime_ns))


# --- committed files ---------------------------------------------------------------------------


def test_committed_log_has_plan_header_and_no_rows() -> None:
    text = COMMITTED_LOG.read_text(encoding="utf-8")
    assert (
        "| Date | Site | Label | Variants | Sim version | Region pkg | Result | Run folder |"
        in text
    )
    assert not [line for line in text.split("\n") if line.startswith("| 20")]


def test_committed_profile_names_ref_v1() -> None:
    assert new_run.profile_names(REPO_ROOT) == ["ref-v1"]


def test_committed_template_has_header_fields_and_checks() -> None:
    text = (REPO_ROOT / "tests" / "visual" / TEMPLATE).read_text(encoding="utf-8")
    for prefix in ("- Site:", "- Date:", "- Label:", "- Tester:"):
        assert prefix in text
    for check in ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"):
        assert f"| {check} |" in text


# --- variants and labels -----------------------------------------------------------------------


def test_parse_variants_accepts_default_pair() -> None:
    assert parse_variants("nofix,static") == ("nofix", "static")


@pytest.mark.parametrize("text", ["", "nofix,bogus", "nofix,nofix"])
def test_parse_variants_refuses_bad_lists(text: str) -> None:
    with pytest.raises(VisualRunError):
        parse_variants(text)


@pytest.mark.parametrize("label", ["a|b", "has space", "../up", "-leading"])
def test_bad_label_is_refused(root: Path, defined_sites: Path, label: str) -> None:
    with pytest.raises(VisualRunError, match="--label"):
        _create(root, defined_sites, label=label)


# --- create ------------------------------------------------------------------------------------


def test_create_builds_tree_and_pending_row(root: Path, defined_sites: Path) -> None:
    run = _create(root, defined_sites)
    assert run == visual_dir(root) / "T1" / "2026-11-22_phase2"
    assert (run / RUN_YAML).is_file()
    assert (run / CHECKLIST).is_file()
    assert (run / "raw" / "nofix").is_dir()
    assert (run / "raw" / "static").is_dir()
    assert not (run / "raw" / "live").exists()

    rows = _log_rows(root)
    assert rows == [
        "| 2026-11-22 | T1 | phase2 | nofix,static | 1.9.24.0 | 0.3.0 "
        "| pending | T1/2026-11-22_phase2 |"
    ]


def test_run_yaml_has_every_required_key(root: Path, defined_sites: Path) -> None:
    import yaml

    run = _create(root, defined_sites)
    data = yaml.safe_load((run / RUN_YAML).read_text(encoding="utf-8"))
    assert set(new_run.REQUIRED_RUN_KEYS) <= set(data)
    assert data["site"] == "T1"
    assert data["date"] == "2026-11-22"
    assert data["label"] == "phase2"
    assert data["packages"] == {"region": "0.3.0", "assets": "none"}
    assert data["graphics_profile"] == "ref-v1"
    assert data["deviations"] == []
    assert data["time_local"] == "12:00"
    assert data["weather"] == "clear"
    assert data["variants"] == ["nofix", "static"]
    assert data["tester"] == "VERIFY"
    assert data["sdk_version"] == "VERIFY"


def test_checklist_header_is_filled_in(root: Path, defined_sites: Path) -> None:
    run = _create(root, defined_sites, tester="Test Person")
    text = (run / CHECKLIST).read_text(encoding="utf-8")
    assert "- Site: T1" in text
    assert "- Date: 2026-11-22" in text
    assert "- Label: phase2" in text
    assert "- Tester: Test Person" in text


def test_second_create_for_same_folder_is_refused(root: Path, defined_sites: Path) -> None:
    _create(root, defined_sites)
    before = _log_rows(root)
    with pytest.raises(VisualRunError, match="already exists"):
        _create(root, defined_sites)
    assert _log_rows(root) == before


def test_same_date_different_label_is_allowed(root: Path, defined_sites: Path) -> None:
    _create(root, defined_sites, label="phase2")
    _create(root, defined_sites, label="phase3")
    assert [split_row(row)[7] for row in _log_rows(root)] == [
        "T1/2026-11-22_phase2",
        "T1/2026-11-22_phase3",
    ]


def test_placeholder_site_is_refused_by_default(root: Path, placeholder_sites: Path) -> None:
    with pytest.raises(VisualRunError, match="placeholder") as info:
        _create(root, placeholder_sites)
    assert "TEST-100" in str(info.value)
    assert not (visual_dir(root) / "T1").exists()
    assert _log_rows(root) == []


def test_placeholder_site_allowed_only_when_asked(root: Path, placeholder_sites: Path) -> None:
    run = _create(root, placeholder_sites, allow_placeholder=True)
    assert run.is_dir()
    assert "site_status: placeholder" in (run / RUN_YAML).read_text(encoding="utf-8")


def test_unknown_site_lists_known_ids(root: Path, defined_sites: Path) -> None:
    with pytest.raises(VisualRunError, match="unknown site 'T9'"):
        create_run(
            "T9",
            day=DAY,
            label=None,
            sim_version="1.9.24.0",
            region_pkg="0.3.0",
            root=root,
            sites_file=defined_sites,
        )


def test_unknown_graphics_profile_is_refused(root: Path, defined_sites: Path) -> None:
    with pytest.raises(VisualRunError, match="graphics profile 'ref-v9'"):
        _create(root, defined_sites, graphics_profile="ref-v9")
    assert not (visual_dir(root) / "T1").exists()


def test_missing_test_log_is_refused(root: Path, defined_sites: Path) -> None:
    (visual_dir(root) / TEST_LOG).unlink()
    with pytest.raises(VisualRunError, match="visual test log not found"):
        _create(root, defined_sites)
    assert not (visual_dir(root) / "T1").exists()


# --- finalize ----------------------------------------------------------------------------------


def test_finalize_orders_by_mtime_and_downscales(root: Path, defined_sites: Path) -> None:
    run = _create(root, defined_sites, variants=("nofix", "static"))
    raw = run / "raw" / "nofix"
    # File names are out of capture order on purpose: mtime decides.
    _write_png(raw / "z_first.png", 4000, 3000, BASE_NS + 1 * 10**9)
    _write_png(raw / "m_second.png", 1000, 750, BASE_NS + 2 * 10**9)
    _write_png(raw / "a_last.png", 800, 600, BASE_NS + 3 * 10**9)
    raw_static = run / "raw" / "static"
    for i, name in enumerate(("01.jpg", "02.jpg", "03.jpg")):
        Image.new("RGB", (640, 480), (1, 2, 3)).save(raw_static / name, format="JPEG")
        os.utime(raw_static / name, ns=(BASE_NS + i * 10**9, BASE_NS + i * 10**9))

    plans = finalize_run(run)

    assert [dst.name for _, dst in plans["nofix"]] == [
        "VP1_street.jpg",
        "VP2_oblique.jpg",
        "VP3_approach.jpg",
    ]
    assert plans["nofix"][0][0].name == "z_first.png"
    vp1 = Image.open(run / "nofix" / "VP1_street.jpg")
    assert vp1.size == (2560, 1920)
    assert vp1.format == "JPEG"
    assert Image.open(run / "nofix" / "VP2_oblique.jpg").size == (1000, 750)
    assert Image.open(run / "nofix" / "VP3_approach.jpg").size == (800, 600)
    assert Image.open(run / "static" / "VP1_street.jpg").size == (640, 480)


def test_finalize_by_name_uses_file_name_order(root: Path, defined_sites: Path) -> None:
    run = _create(root, defined_sites, variants=("nofix",))
    raw = run / "raw" / "nofix"
    _write_png(raw / "z_first.png", 4000, 3000, BASE_NS + 1 * 10**9)
    _write_png(raw / "m_second.png", 1000, 750, BASE_NS + 2 * 10**9)
    _write_png(raw / "a_last.png", 800, 600, BASE_NS + 3 * 10**9)

    plans = finalize_run(run, order="name")

    assert plans["nofix"][0][0].name == "a_last.png"
    assert Image.open(run / "nofix" / "VP1_street.jpg").size == (800, 600)


def test_finalize_refuses_two_screenshots(root: Path, defined_sites: Path) -> None:
    run = _create(root, defined_sites, variants=("nofix",))
    _write_png(run / "raw" / "nofix" / "a.png", 100, 100, BASE_NS + 1 * 10**9)
    _write_png(run / "raw" / "nofix" / "b.png", 100, 100, BASE_NS + 2 * 10**9)
    with pytest.raises(VisualRunError, match="expected exactly 3 screenshots"):
        finalize_run(run)
    assert not (run / "nofix" / "VP1_street.jpg").exists()


def test_finalize_writes_nothing_when_one_variant_is_short(root: Path, defined_sites: Path) -> None:
    run = _create(root, defined_sites, variants=("nofix", "static"))
    for i, name in enumerate(("a.png", "b.png", "c.png")):
        _write_png(run / "raw" / "nofix" / name, 100, 100, BASE_NS + (i + 1) * 10**9)
    _write_png(run / "raw" / "static" / "only.png", 100, 100, BASE_NS + 10**9)
    with pytest.raises(VisualRunError, match="static"):
        finalize_run(run)
    assert not (run / "nofix" / "VP1_street.jpg").exists()


def test_finalize_refuses_equal_mtimes_in_mtime_mode(root: Path, defined_sites: Path) -> None:
    run = _create(root, defined_sites, variants=("nofix",))
    for name in ("a.png", "b.png", "c.png"):
        _write_png(run / "raw" / "nofix" / name, 100, 100, BASE_NS)
    with pytest.raises(VisualRunError, match="share a modification time"):
        finalize_run(run)
    # --order name is the way out and still works.
    finalize_run(run, order="name")
    assert (run / "nofix" / "VP3_approach.jpg").is_file()


def test_finalize_ignores_non_image_files(root: Path, defined_sites: Path) -> None:
    run = _create(root, defined_sites, variants=("nofix",))
    for i, name in enumerate(("a.png", "b.png", "c.png")):
        _write_png(run / "raw" / "nofix" / name, 100, 100, BASE_NS + (i + 1) * 10**9)
    (run / "raw" / "nofix" / "notes.txt").write_text("not a shot", encoding="utf-8")
    finalize_run(run, order="name")
    assert sorted(p.name for p in (run / "nofix").iterdir()) == [
        "VP1_street.jpg",
        "VP2_oblique.jpg",
        "VP3_approach.jpg",
    ]


# --- CLI ---------------------------------------------------------------------------------------


def test_cli_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--help"])
    assert info.value.code == 0
    assert "finalize" in capsys.readouterr().out


def test_cli_default_subcommand_creates_run(
    root: Path,
    defined_sites: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(new_run, "SITES_FILE", defined_sites)
    code = main(
        [
            "--site",
            "T1",
            "--label",
            "phase2",
            "--date",
            "2026-11-22",
            "--sim-version",
            "1.9.24.0",
            "--region-pkg",
            "0.3.0",
            "--root",
            str(root),
        ]
    )
    assert code == 0
    assert (visual_dir(root) / "T1" / "2026-11-22_phase2" / RUN_YAML).is_file()
    out = capsys.readouterr().out
    assert "created" in out
    assert "still VERIFY in run.yaml" in out


def test_cli_refuses_placeholder_with_exit_two(
    root: Path,
    placeholder_sites: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(new_run, "SITES_FILE", placeholder_sites)
    code = main(
        [
            "--site",
            "T1",
            "--sim-version",
            "1.9.24.0",
            "--region-pkg",
            "0.3.0",
            "--root",
            str(root),
        ]
    )
    assert code == 2
    assert "placeholder" in capsys.readouterr().err
    assert not (visual_dir(root) / "T1").exists()


def test_cli_finalize_prints_mapping(
    root: Path,
    defined_sites: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(new_run, "SITES_FILE", defined_sites)
    assert (
        main(
            [
                "--site",
                "T1",
                "--label",
                "phase2",
                "--sim-version",
                "1.9.24.0",
                "--region-pkg",
                "0.3.0",
                "--root",
                str(root),
                "--variants",
                "nofix",
            ]
        )
        == 0
    )
    run = visual_dir(root) / "T1" / "2026-11-22_phase2"
    for i, name in enumerate(("a.png", "b.png", "c.png")):
        _write_png(run / "raw" / "nofix" / name, 100, 100, BASE_NS + (i + 1) * 10**9)
    capsys.readouterr()
    assert main(["finalize", str(run)]) == 0
    out = capsys.readouterr().out
    assert "nofix: " in out and "-> nofix/VP1_street.jpg" in out


def test_cli_finalize_missing_run_exits_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["finalize", str(tmp_path / "nope")]) == 2
    assert "error:" in capsys.readouterr().err
