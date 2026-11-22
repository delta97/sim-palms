"""Self-tests for tests/helpers/golden.py. Every test uses tmp_path as the golden root.

Non-update calls pass ``update=False`` explicitly so the suite also passes when
PALMFIX_UPDATE_GOLDEN=1 and CI are set in the environment.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.golden import (
    EXPECTED_DIR,
    GoldenChecker,
    GoldenMismatch,
    GoldenUpdated,
    assert_golden,
    assert_golden_dir,
    normalize_newlines,
    set_cli_update,
)


@pytest.fixture(autouse=True)
def _clean_update_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test with no CI marker, no env update flag and no --update-golden."""
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("PALMFIX_UPDATE_GOLDEN", raising=False)
    set_cli_update(False)


def _write_golden(root: Path, case: str, rel: str, data: bytes) -> Path:
    path = root / case / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_match_passes(tmp_path: Path) -> None:
    _write_golden(tmp_path, "case", "expected/a.txt", b"hello\nworld\n")
    assert_golden("hello\nworld\n", "case", "expected/a.txt", update=False, root=tmp_path)


def test_one_changed_byte_fails_with_diff(tmp_path: Path) -> None:
    _write_golden(tmp_path, "case", "expected/a.txt", b"hello\nworld\n")
    with pytest.raises(GoldenMismatch) as info:
        assert_golden("hello\nworlD\n", "case", "expected/a.txt", update=False, root=tmp_path)
    message = str(info.value)
    assert "expected/a.txt" in message
    assert "-world" in message
    assert "+worlD" in message


def test_crlf_actual_matches_lf_golden(tmp_path: Path) -> None:
    _write_golden(tmp_path, "case", "expected/a.txt", b"one\ntwo\n")
    assert_golden("one\r\ntwo\r\n", "case", "expected/a.txt", update=False, root=tmp_path)


def test_crlf_golden_matches_lf_actual(tmp_path: Path) -> None:
    _write_golden(tmp_path, "case", "expected/a.txt", b"one\r\ntwo\r\n")
    assert_golden("one\ntwo\n", "case", "expected/a.txt", update=False, root=tmp_path)


def test_raw_mode_compares_bytes(tmp_path: Path) -> None:
    _write_golden(tmp_path, "case", "expected/a.bin", b"one\ntwo\n")
    with pytest.raises(GoldenMismatch):
        assert_golden(
            b"one\r\ntwo\r\n",
            "case",
            "expected/a.bin",
            update=False,
            normalize=None,
            root=tmp_path,
        )


def test_missing_file_fails_with_hint(tmp_path: Path) -> None:
    with pytest.raises(GoldenMismatch) as info:
        assert_golden("x\n", "case", "expected/nope.txt", update=False, root=tmp_path)
    message = str(info.value)
    assert "golden file missing" in message
    assert "pytest --update-golden" in message
    assert "nope.txt" in message


def test_update_writes_lf_and_warns(tmp_path: Path) -> None:
    with pytest.warns(GoldenUpdated):
        assert_golden("one\r\ntwo\r\n", "case", "expected/a.txt", update=True, root=tmp_path)
    written = (tmp_path / "case" / "expected" / "a.txt").read_bytes()
    assert written == b"one\ntwo\n"
    assert_golden("one\ntwo\n", "case", "expected/a.txt", update=False, root=tmp_path)


def test_update_refused_when_ci_set(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "1")
    with pytest.raises(RuntimeError, match="refusing to update golden files in CI"):
        assert_golden("x\n", "case", "expected/a.txt", update=True, root=tmp_path)
    assert not (tmp_path / "case" / "expected" / "a.txt").exists()


def test_env_update_refused_when_ci_set_but_explicit_compare_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CI", "1")
    monkeypatch.setenv("PALMFIX_UPDATE_GOLDEN", "1")
    _write_golden(tmp_path, "case", "expected/a.txt", b"same\n")
    with pytest.raises(RuntimeError, match="refusing to update golden files in CI"):
        assert_golden("same\n", "case", "expected/a.txt", root=tmp_path)
    assert_golden("same\n", "case", "expected/a.txt", update=False, root=tmp_path)


def test_env_flag_enables_update_without_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("PALMFIX_UPDATE_GOLDEN", "1")
    with pytest.warns(GoldenUpdated):
        assert_golden("new\n", "case", "expected/a.txt", root=tmp_path)
    assert (tmp_path / "case" / "expected" / "a.txt").read_bytes() == b"new\n"


def test_dir_reports_missing_and_extra_in_one_message(tmp_path: Path) -> None:
    actual = tmp_path / "out"
    (actual / "sub").mkdir(parents=True)
    (actual / "a.txt").write_text("same\n", encoding="utf-8")
    (actual / "b.txt").write_text("no golden for me\n", encoding="utf-8")
    golden_root = tmp_path / "golden"
    _write_golden(golden_root, "case", f"{EXPECTED_DIR}/a.txt", b"same\n")
    _write_golden(golden_root, "case", f"{EXPECTED_DIR}/c.txt", b"orphan\n")

    with pytest.raises(GoldenMismatch) as info:
        assert_golden_dir(actual, "case", update=False, root=golden_root)
    message = str(info.value)
    assert "b.txt" in message
    assert "c.txt" in message
    assert "2 problem(s)" in message


def test_dir_differing_file_shows_diff(tmp_path: Path) -> None:
    actual = tmp_path / "out"
    actual.mkdir()
    (actual / "a.txt").write_text("alpha\nbeta\n", encoding="utf-8")
    golden_root = tmp_path / "golden"
    _write_golden(golden_root, "case", f"{EXPECTED_DIR}/a.txt", b"alpha\ngamma\n")
    with pytest.raises(GoldenMismatch) as info:
        assert_golden_dir(actual, "case", update=False, root=golden_root)
    assert "-gamma" in str(info.value)
    assert "+beta" in str(info.value)


def test_dir_update_writes_and_removes_extra_but_not_input(tmp_path: Path) -> None:
    actual = tmp_path / "out"
    actual.mkdir()
    (actual / "a.txt").write_text("new a\r\n", encoding="utf-8")
    (actual / "b.txt").write_text("new b\n", encoding="utf-8")
    golden_root = tmp_path / "golden"
    _write_golden(golden_root, "case", f"{EXPECTED_DIR}/a.txt", b"old a\n")
    _write_golden(golden_root, "case", f"{EXPECTED_DIR}/c.txt", b"stale\n")
    input_file = _write_golden(golden_root, "case", "input/palms.geojson", b"{}\n")

    with pytest.warns(GoldenUpdated):
        assert_golden_dir(actual, "case", update=True, root=golden_root)

    expected = golden_root / "case" / EXPECTED_DIR
    assert (expected / "a.txt").read_bytes() == b"new a\n"
    assert (expected / "b.txt").read_bytes() == b"new b\n"
    assert not (expected / "c.txt").exists()
    assert input_file.read_bytes() == b"{}\n"
    assert_golden_dir(actual, "case", update=False, root=golden_root)


def test_dir_pattern_limits_comparison(tmp_path: Path) -> None:
    actual = tmp_path / "out"
    actual.mkdir()
    (actual / "a.xml").write_text("<a/>\n", encoding="utf-8")
    (actual / "notes.log").write_text("ignored\n", encoding="utf-8")
    golden_root = tmp_path / "golden"
    _write_golden(golden_root, "case", f"{EXPECTED_DIR}/a.xml", b"<a/>\n")
    assert_golden_dir(actual, "case", pattern="**/*.xml", update=False, root=golden_root)


def test_diff_is_capped_at_200_lines(tmp_path: Path) -> None:
    old = "".join(f"line {i}\n" for i in range(500))
    new = "".join(f"changed {i}\n" for i in range(500))
    _write_golden(tmp_path, "case", "expected/big.txt", old.encode("utf-8"))
    with pytest.raises(GoldenMismatch) as info:
        assert_golden(new, "case", "expected/big.txt", update=False, root=tmp_path)
    lines = str(info.value).splitlines()
    diff_start = next(i for i, line in enumerate(lines) if line.startswith("---"))
    diff_end = next(i for i, line in enumerate(lines) if line.startswith("run pytest"))
    diff = lines[diff_start:diff_end]
    assert len(diff) <= 200
    assert any("more diff lines not shown" in line for line in diff)


def test_relpath_must_stay_inside_case(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        assert_golden("x\n", "case", "../escape.txt", update=False, root=tmp_path)


def test_normalize_newlines() -> None:
    assert normalize_newlines("a\r\nb\rc\n\n") == "a\nb\nc\n"
    assert normalize_newlines("") == "\n"


def test_checker_binds_root(tmp_path: Path) -> None:
    _write_golden(tmp_path, "case", "expected/a.txt", b"v\n")
    GoldenChecker(tmp_path).check("v\r\n", "case", "expected/a.txt")
