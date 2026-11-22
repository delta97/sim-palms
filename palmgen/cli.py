"""palmgen command line. Stages are imported lazily so ``--help`` stays fast."""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from palmcore.errors import PalmfixError
from palmcore.paths import REGION_RE
from palmgen import __version__, paths
from palmgen.errors import PalmgenError

DEFAULT_ENDPOINT = "https://overpass-api.de/api/interpreter"

Handler = Callable[[argparse.Namespace], int]


def _region_arg(value: str) -> str:
    if not REGION_RE.match(value):
        raise argparse.ArgumentTypeError(
            f"invalid region name {value!r}: use lowercase letters, digits and '-'"
        )
    return value


def _add_region(p: argparse.ArgumentParser) -> None:
    p.add_argument("--region", required=True, type=_region_arg, metavar="NAME")


def _add_path(p: argparse.ArgumentParser, flag: str, help_text: str) -> None:
    p.add_argument(flag, type=Path, default=None, metavar="PATH", help=help_text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="palmgen", description="Generate an MSFS 2024 scenery package from palms.geojson."
    )
    parser.add_argument("--version", action="version", version=f"palmgen {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    b = sub.add_parser("build", help="generate (and compile) the scenery package")
    _add_region(b)
    _add_path(b, "--config", "region config (default: regions/NAME.yaml)")
    _add_path(b, "--palms", "palms.geojson (default: build/scan/NAME/palms.geojson)")
    _add_path(b, "--buildings", "buildings.geojson (default: build/scan/NAME/buildings.geojson)")
    _add_path(b, "--manifest", "asset manifest (default: assets/manifest.json)")
    b.add_argument("--models", choices=["library", "placeholder"], default="library")
    b.add_argument("--placement", choices=["static", "exclusions-only"], default="static")
    b.add_argument("--out", type=Path, default=Path("build"), metavar="DIR")
    b.add_argument(
        "--margin-m",
        type=float,
        default=None,
        metavar="FLOAT",
        help="tuning override: radius = crown_diam_m/2 + margin",
    )
    b.add_argument("--data-version", default=None, metavar="YYYY-MM")
    b.add_argument("--no-airport-mask", action="store_true", help="disable the airport mask")
    b.add_argument("--skip-compile", action="store_true", help="write the project only")
    b.add_argument("--fspackagetool", type=Path, default=None, metavar="PATH")
    b.add_argument("--allow-sim-running", action="store_true")
    b.add_argument("--allow-empty", action="store_true", help="allow a package with zero palms")
    b.add_argument("--timeout", type=int, default=3600, metavar="SECONDS")
    b.add_argument("-v", "--verbose", action="store_true")
    b.set_defaults(handler=_run_build)

    i = sub.add_parser("index", help="export the palm spatial index")
    _add_region(i)
    _add_path(i, "--config", "region config (default: regions/NAME.yaml)")
    _add_path(i, "--palms", "palms.geojson (default: build/scan/NAME/palms.geojson)")
    _add_path(i, "--manifest", "asset manifest (default: assets/manifest.json)")
    i.add_argument("--out", type=Path, default=Path("build"), metavar="DIR")
    i.add_argument("--data-version", default=None, metavar="YYYY-MM")
    i.add_argument("--allow-missing-titles", action="store_true")
    i.set_defaults(handler=_run_index)

    m = sub.add_parser("masks", help="mask data helpers")
    msub = m.add_subparsers(dest="masks_command", required=True, metavar="MASK_COMMAND")
    a = msub.add_parser("airports", help="fetch airport polygons from Overpass")
    _add_region(a)
    _add_path(a, "--config", "region config (default: regions/NAME.yaml)")
    _add_path(a, "--out", "output file (default: data/NAME/masks/airports.geojson)")
    a.add_argument("--endpoint", default=DEFAULT_ENDPOINT, metavar="URL")
    a.set_defaults(handler=_run_airports)
    return parser


def _fill_defaults(opts: argparse.Namespace) -> None:
    """Resolve path flags the user left unset (kept None so --help shows the rule)."""
    region: str = opts.region
    if hasattr(opts, "config") and opts.config is None:
        opts.config = paths.default_config(region)
    if hasattr(opts, "palms") and opts.palms is None:
        opts.palms = paths.default_palms(region)
    if hasattr(opts, "buildings") and opts.buildings is None:
        opts.buildings = paths.default_buildings(region)
    if hasattr(opts, "manifest") and opts.manifest is None:
        opts.manifest = paths.default_manifest()
    if opts.command == "masks" and opts.out is None:
        opts.out = paths.default_airports(region)


def _stage(module: str, func: str, label: str) -> Handler:
    """Import ``module.func`` lazily; a stage that does not exist yet is NotImplementedError."""
    try:
        fn: Handler = getattr(importlib.import_module(module), func)
    except ModuleNotFoundError as exc:
        if exc.name != module:
            raise
        raise NotImplementedError(f"{label} is not implemented yet") from exc
    except AttributeError as exc:
        raise NotImplementedError(f"{label} is not implemented yet") from exc
    return fn


def _run_build(opts: argparse.Namespace) -> int:
    return _stage("palmgen.pipeline", "run_build", "build")(opts)


def _run_index(opts: argparse.Namespace) -> int:
    return _stage("palmgen.spatial_index", "run_index", "index")(opts)


def _run_airports(opts: argparse.Namespace) -> int:
    return _stage("palmgen.masks", "run_fetch_airports", "masks airports")(opts)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        opts = parser.parse_args(argv)
    except SystemExit as exc:  # argparse: --help exits 0, bad usage exits 2
        return exc.code if isinstance(exc.code, int) else 2
    _fill_defaults(opts)
    handler: Handler = opts.handler
    try:
        return int(handler(opts))
    except NotImplementedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (PalmgenError, PalmfixError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
