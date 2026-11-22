"""``palmfx calib``: clicks to intrinsics, time offset, pose bias, depth model (plan 08, A6)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from palmcore.errors import ConfigError
from palmfx.offline.calib import (
    calibrate,
    warnings_for,
    write_calib,
    write_metric_depth,
)
from palmfx.offline.cli import add_standard_args, session_from_args
from palmfx.offline.clicks import default_clicks_path, load_clicks, load_palms
from palmfx.offline.ingest import DEFAULT_MAX_GAP_MS, ingest, parse_drop
from palmfx.offline.session import open_session


def _drop(value: str) -> tuple[int, ...]:
    try:
        return parse_drop(value)
    except ConfigError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "calib",
        help="fit vfov, time offset, pose bias and depth model from clicks.json",
        description=(
            "Fit the camera and depth calibration from calib/clicks.json, write calib/*.json,"
            " re-run ingest with the fitted time offset and write metric frames/NNNNNN.depth.npy."
        ),
    )
    add_standard_args(parser)
    parser.add_argument("--palms", required=True, metavar="GEOJSON", help="palms.geojson")
    parser.add_argument("--clicks", default=None, metavar="JSON", help="default calib/clicks.json")
    parser.add_argument("--max-gap-ms", type=float, default=DEFAULT_MAX_GAP_MS, metavar="MS")
    parser.add_argument(
        "--drop", type=_drop, default=(), metavar="I,J", help="as for `palmfx ingest`"
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    session = session_from_args(args)
    clicks_path = Path(args.clicks) if args.clicks else default_clicks_path(session)
    clicks = load_clicks(clicks_path)
    if not clicks:
        raise ConfigError(f"no clicks in {clicks_path}; run `palmfx clicks` first")
    palms = load_palms(Path(args.palms))
    if not session.frames():  # depth sampling needs frames/NNNNNN.depthraw.npy
        ingest(session, max_gap_ms=args.max_gap_ms, drop=args.drop)

    result = calibrate(session, clicks, palms)
    write_calib(session, result)
    count = ingest(session, max_gap_ms=args.max_gap_ms, drop=args.drop)  # reads time_offset.json
    session = open_session(session.root)
    print(
        f"clicks: {result.n_points}  vfov: {result.vfov_deg:.3f} deg"
        f"  offset: {result.offset_ms:g} ms"
    )
    b = result.bias
    print(
        f"pose bias: heading {b['d_heading_deg']:.3f}  pitch {b['d_pitch_deg']:.3f}"
        f"  bank {b['d_bank_deg']:.3f} deg  body {b['d_body_m']} m"
    )
    print(f"reprojection RMS: {result.rms_px:.2f} px (target {result.rms_target_px:.2f} px)")
    if result.depth_model is not None:
        m = result.depth_model
        print(f"depth model: z = {m.a:.6g} / (d + {m.b:.6g}), relative RMS {100 * m.rms_rel:.2f} %")
        n = write_metric_depth(session, m)
        print(f"wrote metric depth for {n} of {count} frames")
    for msg in warnings_for(result):
        print(f"WARNING: {msg}")
    return 0
