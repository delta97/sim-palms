"""palmscan command line: ``run``, ``priors`` and ``eval`` (stages arrive in later SCAN tasks)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from palmcore.cli_common import add_common_args, add_region_arg, build_context, run_main
from palmcore.errors import EXIT_OK
from palmcore.paths import ensure_dir
from palmscan import __version__
from palmscan.cache import Cache
from palmscan.classify.priors import compute_priors, priors_yaml
from palmscan.config import ScanConfig, scan_config_from_region
from palmscan.http import HttpClient
from palmscan.pipeline import RunOptions, inventory_stages, run, species_level

TOOL = "palmscan"

Handler = Callable[[argparse.Namespace], int]


def _not_implemented(name: str) -> int:
    print(f"palmscan {name}: not implemented yet", file=sys.stderr)
    return 1


def _load(args: argparse.Namespace) -> tuple[ScanConfig, Cache, Path]:
    """Config, download cache and the output directory for ``run``/``priors``."""
    ctx = build_context(args, TOOL)
    cfg = scan_config_from_region(ctx.require_region())
    cache = Cache(
        ctx.paths.data_dir,
        offline=bool(getattr(args, "offline", False)),
        refresh=bool(getattr(args, "refresh", False)),
    )
    out = getattr(args, "out", None)
    if out is not None:
        out_dir = Path(out)
    elif cfg.output_dir is not None:
        out_dir = Path(cfg.output_dir)
        if not out_dir.is_absolute():
            out_dir = ctx.paths.repo_root / out_dir
    else:
        out_dir = ctx.paths.scan_out_dir(cfg.region_name)
    return cfg, cache, out_dir


def _cmd_run(args: argparse.Namespace) -> int:
    cfg, cache, out_dir = _load(args)
    opts = RunOptions(
        out_dir=ensure_dir(out_dir),
        offline=args.offline,
        refresh=args.refresh,
        no_lidar=args.no_lidar,
        only=args.only,
        eval_site=args.eval_site,
    )
    result = run(cfg, opts, cache, HttpClient())
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"palmscan: wrote {result.counts['palms']} palms to {result.palms_path}")
    return result.exit_code


def _cmd_priors(args: argparse.Namespace) -> int:
    cfg, cache, _ = _load(args)
    stages = inventory_stages(cfg, cache, HttpClient())
    computed = compute_priors(species_level(stages.palms))
    for warning in stages.ingest.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    sys.stdout.write(priors_yaml(computed))
    return EXIT_OK


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
