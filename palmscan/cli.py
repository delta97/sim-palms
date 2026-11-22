"""palmscan command line: ``run``, ``priors`` and ``eval``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from palmcore.cli_common import (
    add_common_args,
    add_region_arg,
    build_context,
    build_paths,
    run_main,
)
from palmcore.errors import EXIT_OK, ConfigError
from palmcore.paths import ensure_dir
from palmscan import __version__
from palmscan.cache import Cache
from palmscan.classify.priors import compute_priors, priors_yaml
from palmscan.config import ScanConfig, scan_config_from_region
from palmscan.http import HttpClient
from palmscan.pipeline import RunOptions, inventory_stages, run, species_level
from palmscan.qa.accuracy import (
    accuracy_doc,
    accuracy_section_md,
    evaluate_site,
    write_accuracy,
)

TOOL = "palmscan"

Handler = Callable[[argparse.Namespace], int]


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


def _debug(args: argparse.Namespace) -> bool:
    return int(getattr(args, "verbose", 0) or 0) >= 2


def _cmd_run(args: argparse.Namespace) -> int:
    cfg, cache, out_dir = _load(args)
    opts = RunOptions(
        out_dir=ensure_dir(out_dir),
        offline=args.offline,
        refresh=args.refresh,
        no_lidar=args.no_lidar,
        only=args.only,
        eval_site=args.eval_site,
        debug=_debug(args),
        repo_root=build_paths(args).repo_root,
        sites_root=args.sites_root,
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


def _read_palms(path: Path) -> dict[str, Any]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"palms file not found: {path}") from None
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(doc, dict) or not isinstance(doc.get("features"), list):
        raise ConfigError(f"{path} is not a palms.geojson FeatureCollection")
    return doc


def _cmd_eval(args: argparse.Namespace) -> int:
    """Score a palms.geojson against a site's ground truth (TEST-010) and print the table.

    Exit 0 when the evaluation ran, whatever the scores; threshold failures are in the output
    (and in the JSON), because tuning runs read the numbers rather than a pass/fail status.
    """
    ctx = build_context(args, TOOL, load_region_arg=False)
    palms = _read_palms(Path(args.palms))
    warnings: list[str] = []
    profiles = evaluate_site(
        palms,
        args.site,
        repo_root=ctx.paths.repo_root,
        sites_root=args.sites_root,
        profiles=[args.profile] if args.profile else None,
        radius_m=args.match_radius_m,
        warnings=warnings,
    )
    if not profiles:
        raise ConfigError(
            "palmscan eval needs tests/accuracy (TEST-010) from a repository checkout: "
            + "; ".join(warnings)
        )
    doc = accuracy_doc(args.site, profiles, fallback_height_error_m=None, warnings=warnings)
    sys.stdout.write(accuracy_section_md(doc))
    if args.out is not None:
        out = Path(args.out)
        if out.is_dir():
            print(f"palmscan: wrote {write_accuracy(doc, out)}")
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
            out.write_text(text, encoding="utf-8", newline="\n")
            print(f"palmscan: wrote {out}")
    return EXIT_OK


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
    run.add_argument(
        "--eval-site",
        default=None,
        metavar="SITE",
        help="also score the palms against ground-truth site SITE (tests/accuracy/SITE)",
    )
    run.add_argument(
        "--sites-root",
        type=Path,
        default=None,
        metavar="DIR",
        help="folder holding the ground-truth sites (default tests/accuracy)",
    )
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
    ev.add_argument(
        "--match-radius-m",
        type=float,
        default=None,
        metavar="M",
        help="match radius (default: thresholds.yaml, or the site's meta.yaml)",
    )
    ev.add_argument(
        "--sites-root",
        type=Path,
        default=None,
        metavar="DIR",
        help="folder holding the ground-truth sites (default tests/accuracy)",
    )
    ev.add_argument("--out", type=Path, default=None, metavar="PATH", help="write the JSON here")
    ev.set_defaults(func=_cmd_eval)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run_main(build_parser(), argv)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
