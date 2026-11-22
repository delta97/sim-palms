"""Golden-file comparison with an update flag.

Golden files live in ``tests/golden/<case>/``. GEN owns the cases; this module owns the helper.
Comparison is exact after newline normalisation (CRLF and CR become LF, one trailing LF), so a
Windows checkout cannot cause false failures. Pass ``normalize=None`` for raw bytes.

Usage (in a GEN test)::

    def test_grid_case(golden, tmp_path):
        out = run_generator(input_dir, tmp_path / "out")
        xml = (out / "palms.xml").read_text(encoding="utf-8")
        golden.check(xml, "simple_grid", "expected/palms.xml")  # str or bytes
        golden.check_dir(out, "simple_grid")                    # whole output tree

Accept new output on purpose with ``pytest --update-golden`` (or ``PALMFIX_UPDATE_GOLDEN=1``).
Updates are refused when the ``CI`` environment variable is set.

Layout: ``assert_golden`` takes ``relpath`` relative to the case directory, so pass
``"expected/..."`` to match the case layout. ``assert_golden_dir`` compares the ``expected/``
subtree of the case only, so ``input/`` is never touched by updates.
"""

from __future__ import annotations

import difflib
import os
import warnings
from collections.abc import Callable
from pathlib import Path

from tests.helpers.fixtures import REPO_ROOT

GOLDEN_ROOT: Path = REPO_ROOT / "tests" / "golden"
EXPECTED_DIR = "expected"
UPDATE_ENV = "PALMFIX_UPDATE_GOLDEN"
MAX_DIFF_LINES = 200

Normalizer = Callable[[str], str]

# Set from the --update-golden pytest option by tests/conftest.py.
_cli_update: bool = False


class GoldenMismatch(AssertionError):
    """Actual output differs from the golden file, or the golden file is missing."""


class GoldenUpdated(UserWarning):
    """A golden file was rewritten because the update flag was on."""


def set_cli_update(value: bool) -> None:
    global _cli_update
    _cli_update = bool(value)


def normalize_newlines(text: str) -> str:
    """Convert CRLF and CR to LF and end the text with exactly one LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"


def _update_requested(explicit: bool | None) -> bool:
    """Explicit argument, then the pytest flag, then the environment variable."""
    if explicit is not None:
        wanted = explicit
    elif _cli_update:
        wanted = True
    else:
        wanted = os.environ.get(UPDATE_ENV) == "1"
    if wanted and "CI" in os.environ:
        raise RuntimeError("refusing to update golden files in CI")
    return wanted


def _check_relpath(relpath: str) -> Path:
    rel = Path(relpath)
    if rel.is_absolute() or ".." in rel.parts or not relpath:
        raise ValueError(f"golden relpath must be relative and stay inside the case: {relpath!r}")
    return rel


def _decode(data: bytes) -> str | None:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _canonical(data: str | bytes, normalize: Normalizer | None) -> bytes:
    """Bytes to store or compare. Binary content is never normalised."""
    if normalize is None:
        return data.encode("utf-8") if isinstance(data, str) else data
    text = data if isinstance(data, str) else _decode(data)
    if text is None:
        return data  # type: ignore[return-value]
    return normalize(text).encode("utf-8")


def _diff_lines(expected: bytes, actual: bytes, label: str) -> list[str]:
    """Unified diff of two canonical byte strings, capped at MAX_DIFF_LINES lines."""
    exp_text = expected.decode("utf-8", errors="backslashreplace")
    act_text = actual.decode("utf-8", errors="backslashreplace")
    lines = list(
        difflib.unified_diff(
            exp_text.splitlines(),
            act_text.splitlines(),
            fromfile=f"golden: {label}",
            tofile="actual",
            lineterm="",
        )
    )
    if len(lines) > MAX_DIFF_LINES:
        cut = len(lines) - (MAX_DIFF_LINES - 1)
        lines = [*lines[: MAX_DIFF_LINES - 1], f"... {cut} more diff lines not shown"]
    return lines


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)  # bytes, so no CRLF translation on Windows


def assert_golden(
    actual: str | bytes,
    case: str,
    relpath: str,
    *,
    update: bool | None = None,
    normalize: Normalizer | None = normalize_newlines,
    root: Path = GOLDEN_ROOT,
) -> None:
    """Compare ``actual`` with ``root/case/relpath``; rewrite it when updating."""
    do_update = _update_requested(update)
    path = root / case / _check_relpath(relpath)
    actual_bytes = _canonical(actual, normalize)

    if do_update:
        _write(path, actual_bytes)
        warnings.warn(GoldenUpdated(f"golden file written: {path}"), stacklevel=2)
        return

    if not path.is_file():
        raise GoldenMismatch(
            f"golden file missing: {path}; run pytest --update-golden to create it, "
            "then review the diff"
        )
    expected_bytes = _canonical(path.read_bytes(), normalize)
    if expected_bytes == actual_bytes:
        return
    diff = _diff_lines(expected_bytes, actual_bytes, path.as_posix())
    raise GoldenMismatch(
        f"golden mismatch: {path}\n"
        + "\n".join(diff)
        + "\nrun pytest --update-golden to accept the new output, then review the diff"
    )


def _collect(root_dir: Path, pattern: str) -> dict[str, Path]:
    if not root_dir.is_dir():
        return {}
    return {p.relative_to(root_dir).as_posix(): p for p in root_dir.glob(pattern) if p.is_file()}


def assert_golden_dir(
    actual_dir: Path,
    case: str,
    *,
    pattern: str = "**/*",
    update: bool | None = None,
    normalize: Normalizer | None = normalize_newlines,
    root: Path = GOLDEN_ROOT,
) -> None:
    """Compare every file matching ``pattern`` under ``actual_dir`` with ``root/case/expected``.

    Missing, extra and differing files are all reported in one failure. In update mode every
    actual file is written and extra golden files (matching ``pattern``) are deleted.
    """
    do_update = _update_requested(update)
    golden_dir = root / case / EXPECTED_DIR
    actual_files = _collect(actual_dir, pattern)
    golden_files = _collect(golden_dir, pattern)

    if do_update:
        for rel, src in sorted(actual_files.items()):
            _write(golden_dir / rel, _canonical(src.read_bytes(), normalize))
        extra = sorted(set(golden_files) - set(actual_files))
        for rel in extra:
            (golden_dir / rel).unlink()
        warnings.warn(
            GoldenUpdated(
                f"golden dir written: {golden_dir} "
                f"({len(actual_files)} files written, {len(extra)} extra removed)"
            ),
            stacklevel=2,
        )
        return

    missing = sorted(set(actual_files) - set(golden_files))
    extra = sorted(set(golden_files) - set(actual_files))
    problems: list[str] = []
    for rel in missing:
        problems.append(f"golden file missing: {golden_dir / rel}")
    for rel in extra:
        problems.append(f"extra golden file with no actual output: {golden_dir / rel}")
    for rel in sorted(set(actual_files) & set(golden_files)):
        expected = _canonical(golden_files[rel].read_bytes(), normalize)
        actual = _canonical(actual_files[rel].read_bytes(), normalize)
        if expected != actual:
            diff = _diff_lines(expected, actual, (golden_dir / rel).as_posix())
            problems.append("\n".join(diff))

    if problems:
        raise GoldenMismatch(
            f"golden directory mismatch for case {case!r} ({len(problems)} problem(s)):\n"
            + "\n".join(problems)
            + "\nif the new output is correct, run pytest --update-golden and review the diff"
        )


class GoldenChecker:
    """Fixture object: the helpers bound to one golden root."""

    def __init__(self, root: Path = GOLDEN_ROOT) -> None:
        self.root = root

    def check(
        self,
        actual: str | bytes,
        case: str,
        relpath: str,
        normalize: Normalizer | None = normalize_newlines,
    ) -> None:
        assert_golden(actual, case, relpath, normalize=normalize, root=self.root)

    def check_dir(self, actual_dir: Path, case: str, pattern: str = "**/*") -> None:
        assert_golden_dir(actual_dir, case, pattern=pattern, root=self.root)
