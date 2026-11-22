"""Self-tests for tests/visual/check_run.py: checklist parsing, pass/fail/incomplete, log update.

Runs are built with the real scaffolder in a temp layout; images are generated, never from the sim.
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pytest
import yaml
from PIL import Image

from tests.helpers.fixtures import REPO_ROOT, fixture_path
from tests.visual.check_run import (
    check_run,
    checklist_problems,
    main,
    parse_checklist,
)
from tests.visual.new_run import (
    CHECKLIST,
    PROFILES,
    RUN_YAML,
    TEMPLATE,
    TEST_LOG,
    VIEWPOINT_FILES,
    VisualRunError,
    create_run,
    split_row,
    visual_dir,
)

DAY = dt.date(2026, 11, 22)
CHECK_IDS = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")


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


def _fill(template_text: str, value: str | dict[str, str]) -> str:
    """Fill the VP cells of every C row. ``value`` is one value, or {check: value} overrides."""
    out = []
    for line in template_text.split("\n"):
        if line.startswith("| C") and line.count("|") == 6:
            check, text = split_row(line)[:2]
            cell = value.get(check, "pass") if isinstance(value, dict) else value
            line = f"| {check} | {text} | {cell} | {cell} | {cell} |"
        out.append(line)
    return "\n".join(out)


def _make_run(
    root: Path,
    sites: Path,
    *,
    label: str = "phase2",
    variants: tuple[str, ...] = ("nofix", "static"),
    images: bool = True,
) -> Path:
    run = create_run(
        "T1",
        day=DAY,
        label=label,
        sim_version="1.9.24.0",
        region_pkg="0.3.0",
        tester="Test Person",
        sdk_version="1.8.2",
        variants=variants,
        root=root,
        sites_file=sites,
    )
    if images:
        for variant in variants:
            (run / variant).mkdir(exist_ok=True)
            for name in VIEWPOINT_FILES:
                Image.new("RGB", (32, 32), (9, 9, 9)).save(run / variant / name, format="JPEG")
    return run


def _write_checklist(run: Path, value: str | dict[str, str]) -> None:
    template = (run / CHECKLIST).read_text(encoding="utf-8")
    (run / CHECKLIST).write_text(_fill(template, value), encoding="utf-8")


def _log_row_for(root: Path, folder: str) -> list[str]:
    lines = (visual_dir(root) / TEST_LOG).read_text(encoding="utf-8").split("\n")
    for line in lines:
        cells = split_row(line) if line.startswith("|") else []
        if len(cells) == 8 and cells[7] == folder:
            return cells
    raise AssertionError(f"no log row for {folder}")


def _complete_run(root: Path, sites: Path, label: str = "phase2") -> Path:
    run = _make_run(root, sites, label=label)
    _write_checklist(run, "pass")
    return run


# --- checklist parsing -------------------------------------------------------------------------


def test_committed_template_parses_to_eight_blank_rows() -> None:
    cells = parse_checklist((REPO_ROOT / "tests" / "visual" / TEMPLATE).read_text(encoding="utf-8"))
    assert tuple(cells) == CHECK_IDS
    problems, fails = checklist_problems(cells)
    assert fails == []
    assert len(problems) == 8 * 3
    assert all("is blank" in p for p in problems)


def test_missing_table_header_is_bad_input() -> None:
    with pytest.raises(VisualRunError, match="table header"):
        parse_checklist("no table here\n")


def test_invalid_value_is_a_problem_not_a_fail() -> None:
    cells = {cid: {"VP1": "pass", "VP2": "pass", "VP3": "pass"} for cid in CHECK_IDS}
    cells["C2"]["VP3"] = "ok"
    problems, fails = checklist_problems(cells)
    assert problems == ["checklist.md: C2 VP3 is 'ok'; use pass, fail or na"]
    assert fails == []


def test_missing_check_row_is_a_problem() -> None:
    cells = {cid: {"VP1": "pass", "VP2": "pass", "VP3": "pass"} for cid in CHECK_IDS if cid != "C8"}
    problems, _ = checklist_problems(cells)
    assert problems == ["checklist.md: row C8 is missing"]


# --- check_run ---------------------------------------------------------------------------------


def test_complete_run_passes(root: Path, defined_sites: Path) -> None:
    run = _complete_run(root, defined_sites)
    assert check_run(run) == ("pass", [])


def test_na_cells_count_as_filled(root: Path, defined_sites: Path) -> None:
    run = _make_run(root, defined_sites)
    _write_checklist(run, {"C8": "na"})
    assert check_run(run) == ("pass", [])


def test_one_blank_cell_is_incomplete(root: Path, defined_sites: Path) -> None:
    run = _make_run(root, defined_sites)
    _write_checklist(run, "pass")
    text = (run / CHECKLIST).read_text(encoding="utf-8")
    text = text.replace(
        "| C3 | No floating or sunken palm bases | pass | pass | pass |",
        "| C3 | No floating or sunken palm bases | pass | | pass |",
    )
    (run / CHECKLIST).write_text(text, encoding="utf-8")
    result, problems = check_run(run)
    assert result == "incomplete"
    assert problems == ["checklist.md: C3 VP2 is blank"]


def test_one_fail_cell_fails_the_run(root: Path, defined_sites: Path) -> None:
    run = _make_run(root, defined_sites)
    _write_checklist(run, {"C5": "fail"})
    result, problems = check_run(run)
    assert result == "fail"
    assert "fail cell: C5 at VP1 is fail" in problems
    assert "fail cell: C5 at VP3 is fail" in problems


def test_missing_image_is_incomplete(root: Path, defined_sites: Path) -> None:
    run = _make_run(root, defined_sites)
    _write_checklist(run, "pass")
    (run / "static" / "VP3_approach.jpg").unlink()
    result, problems = check_run(run)
    assert result == "incomplete"
    assert problems == ["missing image static/VP3_approach.jpg"]


def test_images_are_checked_for_every_variant_in_run_yaml(root: Path, defined_sites: Path) -> None:
    run = _make_run(root, defined_sites, variants=("nofix",))
    _write_checklist(run, "pass")
    assert check_run(run) == ("pass", [])


def test_verify_tester_blocks_a_pass(root: Path, defined_sites: Path) -> None:
    run = _complete_run(root, defined_sites)
    data = yaml.safe_load((run / RUN_YAML).read_text(encoding="utf-8"))
    data["tester"] = "VERIFY"
    (run / RUN_YAML).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    result, problems = check_run(run)
    assert result == "incomplete"
    assert problems == ["run.yaml: tester is still VERIFY; fill it in"]


def test_missing_run_yaml_key_is_reported(root: Path, defined_sites: Path) -> None:
    run = _complete_run(root, defined_sites)
    data = yaml.safe_load((run / RUN_YAML).read_text(encoding="utf-8"))
    del data["weather"]
    (run / RUN_YAML).write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    result, problems = check_run(run)
    assert result == "incomplete"
    assert problems == ["run.yaml: missing key weather"]


def test_missing_folder_is_bad_input(tmp_path: Path) -> None:
    with pytest.raises(VisualRunError, match="run folder not found"):
        check_run(tmp_path / "nope")


# --- test log and exit codes -------------------------------------------------------------------


def test_update_log_writes_pass_on_the_right_row_only(root: Path, defined_sites: Path) -> None:
    other = _make_run(root, defined_sites, label="phase1")
    run = _complete_run(root, defined_sites, label="phase2")
    before_other = _log_row_for(root, "T1/2026-11-22_phase1")
    assert main([str(run), "--update-log", "--root", str(root)]) == 0
    assert _log_row_for(root, "T1/2026-11-22_phase2")[6] == "pass"
    assert _log_row_for(root, "T1/2026-11-22_phase1") == before_other
    assert other.is_dir()


def test_update_log_writes_fail(root: Path, defined_sites: Path) -> None:
    run = _make_run(root, defined_sites)
    _write_checklist(run, {"C1": "fail"})
    assert main([str(run), "--update-log", "--root", str(root)]) == 1
    assert _log_row_for(root, "T1/2026-11-22_phase2")[6] == "fail"


def test_incomplete_run_leaves_result_pending(root: Path, defined_sites: Path) -> None:
    run = _make_run(root, defined_sites)
    _write_checklist(run, "pass")
    (run / "nofix" / "VP1_street.jpg").unlink()
    assert main([str(run), "--update-log", "--root", str(root)]) == 1
    assert _log_row_for(root, "T1/2026-11-22_phase2")[6] == "pending"


def test_exit_zero_without_update_log_leaves_log_alone(root: Path, defined_sites: Path) -> None:
    run = _complete_run(root, defined_sites)
    before = (visual_dir(root) / TEST_LOG).read_text(encoding="utf-8")
    assert main([str(run), "--root", str(root)]) == 0
    assert (visual_dir(root) / TEST_LOG).read_text(encoding="utf-8") == before


def test_update_log_refuses_run_without_row(root: Path, defined_sites: Path) -> None:
    run = _complete_run(root, defined_sites)
    lines = (visual_dir(root) / TEST_LOG).read_text(encoding="utf-8").split("\n")
    (visual_dir(root) / TEST_LOG).write_text(
        "\n".join(line for line in lines if "phase2" not in line), encoding="utf-8"
    )
    assert main([str(run), "--update-log", "--root", str(root)]) == 2


def test_help_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--help"])
    assert info.value.code == 0
    assert "--update-log" in capsys.readouterr().out


def test_main_prints_problems_for_incomplete_run(
    root: Path, defined_sites: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run = _make_run(root, defined_sites)
    _write_checklist(run, "pass")
    (run / "static" / "VP2_oblique.jpg").unlink()
    assert main([str(run), "--root", str(root)]) == 1
    out = capsys.readouterr().out
    assert out.startswith("INCOMPLETE")
    assert "missing image static/VP2_oblique.jpg" in out


def test_main_missing_folder_exits_two(root: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(root / "nope"), "--root", str(root)]) == 2
    assert "error:" in capsys.readouterr().err
