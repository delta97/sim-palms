"""Shared pytest harness: markers, run flags, network guard and path fixtures."""

from __future__ import annotations

import ipaddress
import socket
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.helpers.fixtures import FIXTURES_ROOT, REPO_ROOT

NETWORK_DISABLED_MSG = "network disabled in tests: use tests/fixtures or mark @pytest.mark.network"


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("sim-palms")
    group.addoption(
        "--run-network", action="store_true", default=False, help="run tests marked network"
    )
    group.addoption(
        "--run-sim",
        action="store_true",
        default=False,
        help="run tests marked sim (Windows with MSFS 2024 only)",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "network: makes live network calls")
    config.addinivalue_line("markers", "sim: needs Windows + MSFS 2024 + SDK")
    config.addinivalue_line("markers", "slow: takes more than about 10 seconds")


def _socket_plugin_active(config: pytest.Config) -> bool:
    """True when pytest-socket is installed and ``--disable-socket`` is in effect."""
    pm = config.pluginmanager
    has_plugin = pm.hasplugin("socket") or pm.hasplugin("pytest_socket")
    return has_plugin and bool(config.getoption("disable_socket", default=False))


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_network = config.getoption("--run-network")
    run_sim = config.getoption("--run-sim")
    socket_plugin = _socket_plugin_active(config)
    skip_network = pytest.mark.skip(reason="needs network: pass --run-network")
    if not run_sim:
        sim_reason = "needs the sim: pass --run-sim (Windows with MSFS 2024 only)"
    elif sys.platform != "win32":
        sim_reason = "sim tests run only on Windows (pass --run-sim on the sim PC)"
    else:
        sim_reason = ""
    for item in items:
        if "network" in item.keywords:
            if not run_network:
                item.add_marker(skip_network)
            elif socket_plugin:
                item.add_marker(pytest.mark.enable_socket)
        if sim_reason and "sim" in item.keywords:
            item.add_marker(pytest.mark.skip(reason=sim_reason))


def _is_blocked(sock: socket.socket, address: Any) -> bool:
    if sock.family not in (socket.AF_INET, socket.AF_INET6):
        return False
    host = address[0] if isinstance(address, tuple) else address
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    if host in ("localhost", ""):
        return False
    try:
        return not ipaddress.ip_address(str(host).split("%")[0]).is_loopback
    except ValueError:
        return True


@pytest.fixture(autouse=True)
def _network_guard(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Block non-loopback connects unless pytest-socket handles it or the test is marked network."""
    if _socket_plugin_active(request.config) or request.node.get_closest_marker("network"):
        yield
        return

    def _guard(original: Any) -> Any:
        def guarded(self: socket.socket, address: Any, *args: Any, **kwargs: Any) -> Any:
            if _is_blocked(self, address):
                raise RuntimeError(NETWORK_DISABLED_MSG)
            return original(self, address, *args, **kwargs)

        return guarded

    monkeypatch.setattr(socket.socket, "connect", _guard(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", _guard(socket.socket.connect_ex))
    yield


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def fixtures_root() -> Path:
    return FIXTURES_ROOT


@pytest.fixture
def golden_root() -> Path:
    return REPO_ROOT / "tests" / "golden"
