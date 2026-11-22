"""Shared command-line plumbing: common flags, context building and exit-code mapping."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from palmcore.config import load_region
from palmcore.context import RunContext
from palmcore.errors import EXIT_CONFIG, EXIT_INTERRUPTED, EXIT_UNEXPECTED, PalmfixError
from palmcore.log import LOGGER_ROOT, get_logger, new_run_id, setup_logging
from palmcore.paths import Paths

_MAX_ISSUES_LOGGED: Final = 20


def add_common_args(parser: argparse.ArgumentParser) -> None:
    """Add the flags every palmfix tool accepts."""
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-v", "--verbose", action="count", default=0, help="more log output (-vv for debug)"
    )
    group.add_argument("-q", "--quiet", action="store_true", help="only log warnings and errors")
    parser.add_argument("--data-dir", type=Path, default=None, metavar="DIR", help="data/ location")
    parser.add_argument(
        "--build-dir", type=Path, default=None, metavar="DIR", help="build/ location"
    )
    parser.add_argument(
        "--regions-dir", type=Path, default=None, metavar="DIR", help="regions/ location"
    )
    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument(
        "--log-file", type=Path, default=None, metavar="PATH", help="write the log here"
    )
    log_group.add_argument(
        "--no-log-file", action="store_true", help="do not write a log file under build/logs/"
    )


def add_region_arg(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    parser.add_argument(
        "--region",
        required=required,
        default=None,
        metavar="NAME|PATH",
        help="region name (regions/NAME.yaml) or path to a region YAML file",
    )


def build_paths(args: argparse.Namespace) -> Paths:
    """Resolve directories: flag > environment variable > default."""
    return Paths.resolve(
        data_dir=getattr(args, "data_dir", None),
        build_dir=getattr(args, "build_dir", None),
        regions_dir=getattr(args, "regions_dir", None),
    )


def _verbosity(args: argparse.Namespace) -> int:
    if getattr(args, "quiet", False):
        return -1
    return int(getattr(args, "verbose", 0) or 0)


def build_context(
    args: argparse.Namespace, tool: str, *, load_region_arg: bool = True
) -> RunContext:
    """Build paths, load the region (if given), then set up logging."""
    paths = build_paths(args)
    region = None
    region_arg = getattr(args, "region", None)
    if load_region_arg and region_arg:
        region = load_region(region_arg, regions_dir=paths.regions_dir)
    run_id = new_run_id()
    started_at = datetime.now(UTC)
    log_file: Path | None
    if getattr(args, "no_log_file", False):
        log_file = None
    elif getattr(args, "log_file", None) is not None:
        log_file = Path(args.log_file)
    else:
        log_file = paths.logs_dir() / f"{tool}-{run_id}.log"
    setup_logging(_verbosity(args), log_file=log_file)
    return RunContext(
        tool=tool,
        paths=paths,
        run_id=run_id,
        started_at=started_at,
        log_file=log_file,
        region=region,
    )


def _mapped_code(exc: BaseException, error_map: Mapping[type[BaseException], int]) -> int | None:
    """Exit code for the most specific class in ``exc``'s MRO that is in ``error_map``."""
    for cls in type(exc).__mro__:
        if cls in error_map:
            return error_map[cls]
    return None


def _ensure_logging() -> None:
    """Make errors visible when a failure happens before ``build_context`` set up logging."""
    handlers = logging.getLogger(LOGGER_ROOT).handlers
    if not any(getattr(h, "_palmfix", False) for h in handlers):
        setup_logging(0)


def run_main(
    parser: argparse.ArgumentParser,
    argv: Sequence[str] | None,
    *,
    error_map: Mapping[type[BaseException], int] | None = None,
) -> int:
    """Parse ``argv``, run the selected command and turn exceptions into exit codes."""
    overrides: Mapping[type[BaseException], int] = error_map or {}
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse: --help exits 0, bad usage exits 2
        return exc.code if isinstance(exc.code, int) else EXIT_CONFIG
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return EXIT_CONFIG
    try:
        return int(func(args))
    except KeyboardInterrupt as exc:
        _ensure_logging()
        get_logger("cli").error("interrupted")
        code = _mapped_code(exc, overrides)
        return EXIT_INTERRUPTED if code is None else code
    except Exception as exc:
        _ensure_logging()
        log = get_logger("cli")
        code = _mapped_code(exc, overrides)
        if code is None and isinstance(exc, PalmfixError):
            code = exc.exit_code
        if code is None:
            log.error("unexpected error: %s", exc, exc_info=True)
            return EXIT_UNEXPECTED
        log.error("%s", exc)
        for issue in getattr(exc, "issues", [])[:_MAX_ISSUES_LOGGED]:
            log.error("%s", issue)
        return code
