"""The ``palmfix`` utility command line: validate contract files, list and show regions."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import yaml

from palmcore.cli_common import add_common_args, add_region_arg, build_context, run_main
from palmcore.config import RegionConfig, check_regions, list_regions, load_region
from palmcore.contract import validate_palms_file
from palmcore.errors import EXIT_CONFIG, EXIT_CONTRACT, EXIT_OK, ConfigError

TOOL: Final = "palmfix"
MAX_ISSUES_PRINTED: Final = 50


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _cmd_validate(args: argparse.Namespace) -> int:
    ctx = build_context(args, TOOL)
    path: Path = args.path
    if not path.is_file():
        raise ConfigError(f"palms file not found: {path}")
    region = ctx.region
    report = validate_palms_file(
        path,
        region=region.region if region else None,
        bbox=region.bbox.as_tuple() if region else None,
    )
    failed = bool(report.errors) or (args.strict and bool(report.warnings))
    code = EXIT_CONTRACT if failed else EXIT_OK
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return code

    for issue in report.issues[:MAX_ISSUES_PRINTED]:
        print(issue)
    hidden = len(report.issues) - MAX_ISSUES_PRINTED
    if hidden > 0:
        print(f"... and {hidden} more")
    n_err, n_warn = len(report.errors), len(report.warnings)
    if failed:
        print(
            f"FAILED: {_plural(n_err, 'error')}, {_plural(n_warn, 'warning')} "
            f"in {_plural(report.feature_count, 'feature')}"
        )
    else:
        print(
            f"OK: {_plural(report.feature_count, 'feature')}, "
            f"schema {report.schema_version}, {_plural(n_warn, 'warning')}"
        )
    return code


def _region_line(name: str, cfg: RegionConfig) -> str:
    return f"{name:<20} {cfg.id_prefix:<4} {cfg.bbox.to_list()}"


def _cmd_regions(args: argparse.Namespace) -> int:
    ctx = build_context(args, TOOL, load_region_arg=False)
    regions_dir = ctx.paths.regions_dir
    if args.check:
        problems = check_regions(regions_dir)
        if problems:
            for problem in problems:
                print(f"error: {problem}")
            return EXIT_CONFIG
        print(f"OK: {_plural(len(list_regions(regions_dir)), 'region')}")
        return EXIT_OK
    for name in list_regions(regions_dir):
        try:
            cfg = load_region(name, regions_dir=regions_dir)
        except ConfigError as exc:
            ctx.log.warning("%s", exc)
            print(f"{name:<20} (invalid; run 'palmfix regions --check')")
        else:
            print(_region_line(name, cfg))
    return EXIT_OK


def _cmd_config(args: argparse.Namespace) -> int:
    cfg = build_context(args, TOOL).require_region()
    data = cfg.to_dict()
    if args.format == "json":
        print(json.dumps(data, indent=2, default=str))
    else:
        print(yaml.safe_dump(data, sort_keys=False, default_flow_style=False).rstrip())
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL, description="Check palms.geojson files and region configs."
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p_validate = sub.add_parser("validate", help="validate a palms.geojson file")
    p_validate.add_argument("path", type=Path, metavar="PATH", help="palms.geojson to check")
    add_region_arg(p_validate, required=False)
    p_validate.add_argument("--strict", action="store_true", help="treat warnings as failures")
    p_validate.add_argument("--json", action="store_true", help="print the report as JSON only")
    add_common_args(p_validate)
    p_validate.set_defaults(func=_cmd_validate)

    p_regions = sub.add_parser("regions", help="list region configs")
    p_regions.add_argument(
        "--check", action="store_true", help="load every region and report problems"
    )
    add_common_args(p_regions)
    p_regions.set_defaults(func=_cmd_regions)

    p_config = sub.add_parser("config", help="print a normalised region config")
    add_region_arg(p_config, required=True)
    p_config.add_argument("--format", choices=["yaml", "json"], default="yaml")
    add_common_args(p_config)
    p_config.set_defaults(func=_cmd_config)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    return run_main(build_parser(), argv)
