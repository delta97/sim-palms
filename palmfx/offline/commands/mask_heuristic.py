"""``palmfx mask-heuristic``: blob masks from raw depth and colour (plan 08, A8).

Reads ``frames.jsonl`` (frames with a ``depthraw`` file) and writes ``masks/heuristic/``. With
``--debug`` also writes ``masks/heuristic/debug/NNNNNN.png`` (components yellow, kept green,
rejected red with reason initials H/A/F/E: height, aspect, fill, edge support) and the per-component
diagnostics in the mask JSON under ``params.debug``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np

from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmfx.offline.cli import add_standard_args, session_from_args
from palmfx.offline.mask_heuristic import HeuristicParams, debug_overlay, heuristic_masks
from palmfx.offline.session import Session, read_image, write_image, write_mask

log = get_logger(__name__)


def session_reversed(session: Session) -> bool:
    """``session.json`` key ``reversed`` (default True). VERIFY: real MSFS 2024 depth convention."""
    value = session.meta.get("reversed", True)
    if not isinstance(value, bool):
        raise ConfigError(f"session.json 'reversed' must be true or false, got {value!r}")
    return value


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "mask-heuristic",
        help="blob masks from raw depth and colour (no palm database, no calibration)",
        description=(
            "Detect blobs as narrow, nearer, olive-green objects in frames/*.depthraw.npy and "
            "write masks/heuristic/. Thresholds come from config/heuristic.yaml."
        ),
    )
    add_standard_args(parser)
    parser.add_argument("--config", type=Path, default=None, metavar="YAML")
    parser.add_argument("--debug", action="store_true", help="write masks/heuristic/debug/*.png")
    parser.add_argument(
        "--occluder", type=Path, default=None, metavar="PNG", help="static occluder mask"
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    session = session_from_args(args)
    params = HeuristicParams.from_yaml(args.config)
    reversed_z = session_reversed(session)
    occluder = None
    if args.occluder is not None:
        occluder = read_image(Path(args.occluder))
        if occluder.ndim != 2:
            raise ConfigError(f"--occluder must be a single-channel PNG: {args.occluder}")

    frames = [f for f in session.frames() if f.depthraw is not None]
    if not frames:
        raise ConfigError("no frames with raw depth; run 'palmfx ingest' first")
    out_dir = session.path("masks", "heuristic")
    total = 0
    for rec in frames:
        assert rec.depthraw is not None
        color = read_image(rec.color)
        depth = np.load(rec.depthraw)
        ms = heuristic_masks(
            color, depth, params, reversed=reversed_z, occluder=occluder, debug=args.debug
        )
        write_mask(out_dir, rec.idx, ms)
        if args.debug:
            write_image(out_dir / "debug" / f"{rec.idx:06d}.png", debug_overlay(color, ms))
        total += len(ms.instances)
    print(f"mask-heuristic: {len(frames)} frames, {total} instances -> {out_dir}")
    return 0
