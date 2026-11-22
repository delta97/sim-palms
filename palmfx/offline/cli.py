"""The ``palmfx`` command line. Subcommands are discovered from ``palmfx.offline.commands``."""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

from palmcore.cli_common import add_common_args, run_main
from palmcore.log import get_logger
from palmfx.offline import __version__, commands
from palmfx.offline.session import Session, open_session

TOOL = "palmfx"

log = get_logger(__name__)


def add_standard_args(parser: argparse.ArgumentParser) -> None:
    """Add ``--session`` and the shared palmfix flags to a subcommand parser."""
    add_common_args(parser)
    parser.add_argument(
        "--session",
        required=True,
        metavar="DIR",
        help="session directory, data/fx/<session_id>",
    )


def session_from_args(args: argparse.Namespace) -> Session:
    """Open the session named by ``--session``."""
    return open_session(Path(args.session))


def discover_commands() -> list[ModuleType]:
    """Import every module in ``palmfx.offline.commands`` (sorted by name)."""
    found: list[ModuleType] = []
    for info in sorted(pkgutil.iter_modules(commands.__path__), key=lambda i: i.name):
        name = f"{commands.__name__}.{info.name}"
        try:
            found.append(importlib.import_module(name))
        except ImportError as exc:
            log.warning("skipping command module %s: %s", name, exc)
    return found


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL, description="Offline image-layer experiment tools (Stage A)."
    )
    parser.add_argument("--version", action="version", version=f"{TOOL} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    for module in discover_commands():
        register = getattr(module, "register", None)
        if not callable(register):
            log.warning("command module %s has no register(); skipped", module.__name__)
            continue
        register(sub)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run_main(build_parser(), argv)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
