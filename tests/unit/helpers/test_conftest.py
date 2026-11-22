"""Self-tests for tests/conftest.py, run in a subprocess with the conftest copied in."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers.fixtures import REPO_ROOT

pytest_plugins = ["pytester"]

CONFTEST = (REPO_ROOT / "tests" / "conftest.py").read_text(encoding="utf-8")

SUITE = """
import socket
import pytest

@pytest.mark.network
def test_net(monkeypatch):
    monkeypatch.setattr(socket.socket, "connect", lambda self, addr: None)
    socket.socket().connect(("203.0.113.1", 80))

@pytest.mark.sim
def test_sim():
    pass

def test_unmarked_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.01)
    with pytest.raises(RuntimeError, match="network disabled in tests"):
        s.connect(("203.0.113.1", 80))
    s.close()

def test_loopback_not_blocked():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.01)
    with pytest.raises(OSError):
        s.connect(("127.0.0.1", 9))
    s.close()
"""


@pytest.fixture
def inner(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> pytest.Pytester:
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    pytester.makeconftest(CONFTEST + "\nsys.platform = 'linux'\n")
    pytester.makepyfile(test_inner=SUITE)
    return pytester


def _run(pt: pytest.Pytester, *args: str) -> pytest.RunResult:
    return pt.runpytest_subprocess("-p", "no:cacheprovider", "-rs", *args)


def test_network_skipped_without_flag(inner: pytest.Pytester) -> None:
    result = _run(inner, "-k", "test_net")
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*pass --run-network*"])


def test_network_runs_with_flag(inner: pytest.Pytester) -> None:
    _run(inner, "--run-network", "-k", "test_net").assert_outcomes(passed=1)


def test_sim_skipped_on_non_windows_even_with_flag(inner: pytest.Pytester) -> None:
    _run(inner, "-k", "test_sim").assert_outcomes(skipped=1)
    result = _run(inner, "--run-sim", "-k", "test_sim")
    result.assert_outcomes(skipped=1)
    result.stdout.fnmatch_lines(["*only on Windows*"])


def test_sim_runs_on_windows_with_flag(inner: pytest.Pytester) -> None:
    conftest = Path(inner.path) / "conftest.py"
    conftest.write_text(CONFTEST + "\nsys.platform = 'win32'\n", encoding="utf-8")
    _run(inner, "--run-sim", "-k", "test_sim").assert_outcomes(passed=1)
    _run(inner, "-k", "test_sim").assert_outcomes(skipped=1)


def test_unmarked_public_connect_blocked_and_loopback_allowed(inner: pytest.Pytester) -> None:
    _run(inner, "-k", "unmarked or loopback").assert_outcomes(passed=2)


def test_markers_registered(inner: pytest.Pytester) -> None:
    result = _run(inner, "--markers")
    result.stdout.fnmatch_lines(
        ["*@pytest.mark.network*", "*@pytest.mark.sim*", "*@pytest.mark.slow*"]
    )
