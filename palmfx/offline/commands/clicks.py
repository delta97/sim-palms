"""``palmfx clicks``: interactive correspondence clicking (plan 08, A6). Needs a display."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from palmcore.errors import ConfigError
from palmfx.offline.cli import add_standard_args, session_from_args
from palmfx.offline.clicks import default_clicks_path, load_palms, run_click_ui


def _frames(value: str) -> tuple[int, ...]:
    if not re.fullmatch(r"\s*\d+(\s*,\s*\d+)*\s*", value):
        raise argparse.ArgumentTypeError(f"expected comma-separated frame indices, got {value!r}")
    return tuple(int(p) for p in value.split(","))


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "clicks",
        help="click palm bases/tops on frames to make calib/clicks.json (needs a display)",
        description=(
            "Show each frame with projected palm points; left click a point, then type"
            " 'PALM_ID base|top' or 'w LAT LON H' in the terminal. Keys: u undo, n next, q quit."
            " Saves after every click and resumes from an existing clicks.json."
        ),
    )
    add_standard_args(parser)
    parser.add_argument("--frames", required=True, type=_frames, metavar="0,15,30")
    parser.add_argument("--palms", required=True, metavar="GEOJSON", help="palms.geojson")
    parser.add_argument("--out", default=None, metavar="JSON", help="default calib/clicks.json")
    parser.add_argument(
        "--vfov-deg", type=float, default=60.0, help="vfov for the overlay (default 60)"
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    session = session_from_args(args)
    out = Path(args.out) if args.out else default_clicks_path(session)
    try:
        clicks = run_click_ui(
            session, args.frames, load_palms(Path(args.palms)), out, args.vfov_deg
        )
    except ImportError as exc:
        raise ConfigError(f"the click UI needs matplotlib (pip install '.[fx]'): {exc}") from exc
    print(f"{len(clicks)} clicks in {out}")
    return 0
