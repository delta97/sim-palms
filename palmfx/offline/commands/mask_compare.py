"""``palmfx mask-compare``: score one mask method against another (plan 08, A9).

``--a`` is the method under test (the prediction), ``--b`` the reference, e.g. ``hand``. Writes
``metrics/mask-<a>-vs-<b>.json`` in the session and prints a five-line summary.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmfx.offline.cli import add_standard_args, session_from_args
from palmfx.offline.mask_metrics import DEFAULT_IOU_THR, compare_dirs, summary_lines
from palmfx.offline.session import read_image

log = get_logger(__name__)

_METHOD = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _method_name(value: str) -> str:
    if not _METHOD.match(value):
        raise argparse.ArgumentTypeError(f"method must match {_METHOD.pattern}: {value!r}")
    return value


def _iou_thr(value: str) -> float:
    try:
        thr = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from exc
    if not 0.0 < thr <= 1.0:
        raise argparse.ArgumentTypeError(f"--iou-thr must be in (0, 1], got {value}")
    return thr


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "mask-compare",
        help="score mask method --a against reference --b (pixel IoU, instance P/R)",
        description=(
            "Compare two mask methods in a session. --a is the prediction (method under test), "
            "--b the reference (for example hand). Frames present in only one method are skipped."
        ),
    )
    add_standard_args(parser)
    parser.add_argument("--a", required=True, type=_method_name, metavar="METHOD")
    parser.add_argument("--b", required=True, type=_method_name, metavar="METHOD")
    parser.add_argument(
        "--iou-thr",
        type=_iou_thr,
        default=DEFAULT_IOU_THR,
        metavar="X",
        help=f"instance match threshold in (0, 1] (default {DEFAULT_IOU_THR})",
    )
    parser.add_argument(
        "--occluder",
        type=Path,
        default=None,
        metavar="PNG",
        help="static occluder mask; non-zero pixels are removed from both masks",
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    session = session_from_args(args)
    dir_a = session.path("masks", args.a)
    dir_b = session.path("masks", args.b)
    occluder = None
    if args.occluder is not None:
        occluder = read_image(Path(args.occluder))
        if occluder.ndim != 2:
            raise ConfigError(f"--occluder must be a single-channel PNG: {args.occluder}")

    result = compare_dirs(dir_a, dir_b, occluder=occluder, iou_thr=args.iou_thr)
    summary = result["summary"]
    if summary["frames_compared"] == 0:
        raise ConfigError(f"no frame is present in both {args.a!r} and {args.b!r}")

    doc = {
        "a": args.a,
        "b": args.b,
        "session_id": session.meta.get("session_id", session.root.name),
        "occluder": None if args.occluder is None else str(args.occluder),
        **result,
    }
    out = session.path("metrics", f"mask-{args.a}-vs-{args.b}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    log.info("wrote %s", out)

    for line in summary_lines(summary):
        print(line)
    print(f"wrote {out}")
    return 0
