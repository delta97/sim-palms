"""``palmfx inpaint``: erase masked blobs with LaMa or the Telea baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmfx.offline.cli import add_standard_args, session_from_args
from palmfx.offline.inpaint import (
    Inpainter,
    LamaInpainter,
    TeleaInpainter,
    Tile,
    inpaint_tiled,
)
from palmfx.offline.session import read_image, read_mask, write_image

log = get_logger(__name__)


def parse_frames(spec: str | None) -> tuple[int, int] | None:
    """Parse ``a-b`` (inclusive) or a single index ``a``."""
    if spec is None:
        return None
    try:
        lo_s, _, hi_s = spec.partition("-")
        lo = int(lo_s)
        hi = int(hi_s) if hi_s else lo
    except ValueError:
        raise ConfigError(f"--frames must be 'a-b' or 'a', got {spec!r}") from None
    if lo < 0 or hi < lo:
        raise ConfigError(f"--frames range is empty or negative: {spec!r}")
    return lo, hi


def _device(requested: str | None, backend: str) -> str:
    if backend == "telea":
        return "cpu"
    if requested is not None:
        return requested
    try:
        import torch  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def _run(args: argparse.Namespace) -> int:
    session = session_from_args(args)
    frames_range = parse_frames(args.frames)
    records = [
        r
        for r in session.frames()
        if frames_range is None or frames_range[0] <= r.idx <= frames_range[1]
    ]
    if not records:
        raise ConfigError("no frames selected (is the session ingested? check --frames)")
    device = _device(args.device, args.backend)
    inpainter: Inpainter
    if args.backend == "lama":
        weights = (
            Path(args.weights) if args.weights else session.root.parent / "models" / "big-lama.pt"
        )
        inpainter = LamaInpainter(weights, device, trust_unlisted_checksum=args.trust_weights)
    else:
        inpainter = TeleaInpainter()

    tag = f"{args.mask}-{args.backend}"
    mask_dir = session.path("masks", args.mask)
    out_dir = session.path("inpaint", tag)
    tile_seconds: list[float] = []
    per_frame: list[dict[str, Any]] = []
    for rec in records:
        rgb = read_image(rec.color)
        masks = read_mask(mask_dir, rec.idx)
        seconds: list[float] = []

        def record(_tile: Tile, s: float, acc: list[float] = seconds) -> None:
            acc.append(s)

        out = inpaint_tiled(
            rgb,
            masks.union,
            inpainter,
            on_tile=record,
        )
        write_image(out_dir / f"{rec.idx:06d}.png", out)
        tile_seconds.extend(seconds)
        per_frame.append({"idx": rec.idx, "tiles": len(seconds), "seconds": seconds})
        log.info("frame %d: %d tile(s)", rec.idx, len(seconds))

    timing = {
        "backend": args.backend,
        "mask": args.mask,
        "device": device,
        "frames": len(records),
        "tiles_total": len(tile_seconds),
        "tiles_per_frame": len(tile_seconds) / len(records),
        "seconds_per_tile_mean": sum(tile_seconds) / len(tile_seconds) if tile_seconds else 0.0,
        "seconds_per_tile_max": max(tile_seconds, default=0.0),
        "per_frame": per_frame,
    }
    metrics = session.path("metrics", f"inpaint-{tag}-timing.json")
    metrics.parent.mkdir(parents=True, exist_ok=True)
    metrics.write_text(json.dumps(timing, indent=2) + "\n", encoding="utf-8", newline="\n")
    log.info("wrote %d frame(s) to %s", len(records), out_dir)
    return 0


def register(subparsers: Any) -> None:
    p = subparsers.add_parser("inpaint", help="erase masked blobs (LaMa or Telea baseline)")
    add_standard_args(p)
    p.add_argument("--mask", required=True, metavar="METHOD", help="mask method directory name")
    p.add_argument("--backend", choices=["lama", "telea"], required=True)
    p.add_argument("--device", choices=["cuda", "cpu"], default=None, help="lama only")
    p.add_argument("--frames", default=None, metavar="A-B", help="inclusive frame index range")
    p.add_argument(
        "--weights", default=None, metavar="FILE", help="default: data/fx/models/big-lama.pt"
    )
    p.add_argument(
        "--trust-weights",
        action="store_true",
        help="allow weights whose sha256 is not yet recorded in models.lock.json",
    )
    p.set_defaults(func=_run)
