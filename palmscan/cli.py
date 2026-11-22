"""palmscan command line: ``run``, ``priors`` and ``eval`` (stages arrive in later SCAN tasks)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from palmcore.cli_common import add_common_args, add_region_arg, run_main
from palmscan import __version__

TOOL = "palmscan"

Handler = Callable[[argparse.Namespace], int]


def _not_implemented(name: str) -> int:
    print(f"palmscan {name}: not implemented yet", file=sys.stderr)
    return 1


def _cmd_run(args: argparse.Namespace) -> int:
    return _not_implemented("run")


def _cmd_priors(args: argparse.Namespace) -> int:
    return _not_implemented("priors")


def _cmd_eval(args: argparse.Namespace) -> int:
    return _not_implemented("eval")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL, description="Build palms.geojson from public tree and LiDAR data."
    )
    parser.add_argument("--version", action="version", version=f"{TOOL} {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    run = sub.add_parser("run", help="run the detection pipeline for a region")
    add_common_args(run)
    add_region_arg(run)
    run.add_argument(
        "--out", type=Path, default=None, metavar="DIR", help="output dir (default build/scan/NAME)"
    )
    run.add_argument("--offline", action="store_true", help="never use the network; cache only")
    run.add_argument("--refresh", action="store_true", help="re-download even if cached")
    run.add_argument("--no-lidar", action="store_true", help="skip the LiDAR stage")
    run.add_argument(
        "--only",
        choices=["inventory", "lidar"],
        default=None,
        help="run only one detection source",
    )
    run.add_argument("--eval-site", default=None, metavar="SITE", help="also evaluate on SITE")
    run.set_defaults(func=_cmd_run)

    priors = sub.add_parser("priors", help="compute species priors from the region's inventory")
    add_common_args(priors)
    add_region_arg(priors)
    priors.add_argument("--offline", action="store_true", help="never use the network")
    priors.set_defaults(func=_cmd_priors)

    ev = sub.add_parser("eval", help="score a palms.geojson against site ground truth")
    add_common_args(ev)
    ev.add_argument("--palms", type=Path, required=True, metavar="PATH")
    ev.add_argument("--site", required=True, metavar="SITE")
    ev.add_argument("--profile", default=None, metavar="NAME")
    ev.add_argument("--match-radius-m", type=float, default=3.0, metavar="M")
    ev.add_argument("--out", type=Path, default=None, metavar="PATH")
    ev.set_defaults(func=_cmd_eval)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run_main(build_parser(), argv)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
