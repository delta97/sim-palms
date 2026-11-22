"""``palmfx ingest``: raw capture to ``frames/`` + ``frames.jsonl`` (plan 08, A4)."""

from __future__ import annotations

import argparse
from typing import Any

from palmcore.errors import ConfigError
from palmfx.offline.cli import add_standard_args, session_from_args
from palmfx.offline.ingest import DEFAULT_MAX_GAP_MS, POSE_COLUMNS, ingest, parse_drop


def _drop(value: str) -> tuple[int, ...]:
    try:
        return parse_drop(value)
    except ConfigError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _column(value: str) -> tuple[str, str]:
    key, sep, col = value.partition("=")
    if not sep or key not in POSE_COLUMNS or not col:
        raise argparse.ArgumentTypeError(
            f"expected CANONICAL=CSV_COLUMN with CANONICAL in {sorted(POSE_COLUMNS)}: {value!r}"
        )
    return key, col


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "ingest",
        help="raw/ to frames/ + frames.jsonl (decode depth, interpolate poses)",
        description=(
            "Pair ReShade screenshots with triggers, decode packed depth, interpolate the pose"
            " log onto frame times and write frames/ and frames.jsonl. The time offset comes"
            " from calib/time_offset.json when present."
        ),
    )
    add_standard_args(parser)
    parser.add_argument("--max-gap-ms", type=float, default=DEFAULT_MAX_GAP_MS, metavar="MS")
    parser.add_argument(
        "--drop",
        type=_drop,
        default=(),
        metavar="I,J",
        help="trigger frame indices that produced no screenshot",
    )
    parser.add_argument("--before-suffix", default=None, metavar="S", help="clean colour suffix")
    parser.add_argument("--after-suffix", default=None, metavar="S", help="packed depth suffix")
    parser.add_argument(
        "--offset-ms", type=float, default=None, metavar="MS", help="override the time offset"
    )
    parser.add_argument(
        "--pose-column",
        action="append",
        type=_column,
        default=[],
        metavar="NAME=COL",
        help="map a canonical pose field to a poses.csv column (repeatable)",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    session = session_from_args(args)
    count = ingest(
        session,
        max_gap_ms=args.max_gap_ms,
        drop=args.drop,
        before_suffix=args.before_suffix,
        after_suffix=args.after_suffix,
        offset_ms=args.offset_ms,
        columns=dict(args.pose_column),
    )
    print(f"ingested {count} frames into {session.path('frames')}")
    return 0
