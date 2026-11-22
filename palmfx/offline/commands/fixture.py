"""``palmfx fixture``: a small downscaled raw session for the committed sample set (plan 08, A4).

The output is a *raw* session (so tests exercise ingest), renumbered from 0 with the original
frame indices in ``session.json`` as ``source_frames``. Colour is area-averaged; packed depth is
stride-sampled (nearest) because packed values cannot be averaged, so every decoded depth value
in the fixture exists in the source. Masks and the occluder are sampled the same way. Hand-mask
instance files are dropped: the reader derives instances from the union mask.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmfx.offline.camera import LocalFrame
from palmfx.offline.cli import add_standard_args, session_from_args
from palmfx.offline.ingest import (
    match_frames,
    pair_screenshots,
    parse_drop,
    read_pose_rows,
    read_triggers,
    suffixes,
)
from palmfx.offline.session import Session, new_session, read_image, write_image

log = get_logger(__name__)

MAX_BYTES = 5 * 1024 * 1024
POSE_WINDOW_NS = 200_000_000
PALM_RADIUS_M = 2000.0


def sample_nearest(img: NDArray[Any], width: int, height: int) -> NDArray[Any]:
    """Centre-sampled nearest-neighbour resize; values are never blended."""
    h, w = img.shape[:2]
    xs = np.minimum(((np.arange(width) + 0.5) * w / width).astype(np.int64), w - 1)
    ys = np.minimum(((np.arange(height) + 0.5) * h / height).astype(np.int64), h - 1)
    out: NDArray[Any] = img[ys[:, None], xs[None, :]]
    return out


def _dir_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def _write_csv(path: Path, header: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _write_json(path: Path, doc: Any) -> None:
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


def _clip_palms(src: Path, dst: Path, pose_rows: Sequence[dict[str, Any]], radius_m: float) -> int:
    try:
        doc = json.loads(src.read_text(encoding="utf-8"))
        features = list(doc["features"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigError(f"cannot read palms GeoJSON {src}: {exc}") from exc
    if not pose_rows:
        raise ConfigError("no pose rows near the selected frames; cannot clip palms")
    frame = LocalFrame(pose_rows[0]["lat_deg"], pose_rows[0]["lon_deg"], 0.0)
    cams = frame.to_enu([r["lat_deg"] for r in pose_rows], [r["lon_deg"] for r in pose_rows], 0.0)
    cams_xy = cams[:, :2]
    kept: list[Any] = []
    for feat in features:
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"][:2]
        xy = frame.to_enu(lat, lon, 0.0)[0, :2]
        if float(np.min(np.hypot(*(cams_xy - xy).T))) <= radius_m:
            kept.append(feat)
    doc["features"] = kept
    _write_json(dst, doc)
    return len(kept)


def _copy_calib(session: Session, fixture: Session, scale: float, w: int, h: int) -> None:
    src = session.path("calib")
    if not src.is_dir():
        return
    dst = fixture.path("calib")
    for path in sorted(src.iterdir()):
        if not path.is_file():
            continue
        if path.name == "intrinsics.json":
            doc = json.loads(path.read_text(encoding="utf-8"))
            for key in ("fx", "fy", "cx", "cy"):
                if key in doc:
                    doc[key] = doc[key] * scale
            doc["width"], doc["height"] = w, h
            _write_json(dst / path.name, doc)
        elif path.name == "static_occluder.png":
            write_image(dst / path.name, sample_nearest(read_image(path), w, h))
        else:
            shutil.copyfile(path, dst / path.name)


def _copy_hand_masks(
    session: Session, fixture: Session, frames: Sequence[int], w: int, h: int
) -> None:
    src = session.path("masks", "hand")
    for new_idx, src_idx in enumerate(frames):
        path = src / f"{src_idx:06d}.png"
        if path.is_file():
            write_image(
                fixture.path("masks", "hand", f"{new_idx:06d}.png"),
                sample_nearest(read_image(path), w, h),
            )


def build_fixture(
    session: Session,
    out: Path,
    frames: Sequence[int],
    scale: float,
    palms: Path | None = None,
    drop: Sequence[int] = (),
    before_suffix: str | None = None,
    after_suffix: str | None = None,
    max_bytes: int = MAX_BYTES,
) -> Path:
    """Write the fixture session to ``out`` and return it. Raises ``ConfigError`` over budget."""
    if not 0.0 < scale <= 1.0:
        raise ConfigError(f"--scale must be in (0, 1], got {scale}")
    if not frames or len(set(frames)) != len(frames):
        raise ConfigError("--frames needs distinct frame indices")
    b_suf, a_suf = suffixes(session, before_suffix, after_suffix)
    pairs, _ = pair_screenshots(session, b_suf, a_suf)
    matched = {i: (t, p) for i, t, p in match_frames(read_triggers(session), pairs, drop)}
    missing = [i for i in frames if i not in matched]
    if missing:
        raise ConfigError(f"frames not available in the session: {missing}")

    out = Path(out)
    existed = out.exists()
    first = read_image(matched[frames[0]][1].before)
    new_w = max(1, round(first.shape[1] * scale))
    new_h = max(1, round(first.shape[0] * scale))
    meta = dict(session.meta)
    meta.update(
        {
            "session_id": out.name,
            "source_session_id": session.meta.get("session_id", session.root.name),
            "source_frames": list(frames),
            "fixture_scale": scale,
            "resolution": [new_w, new_h],
            "reshade_suffixes": {"before": b_suf, "after": a_suf},
        }
    )
    try:
        fixture = new_session(out, meta)
        reshade = fixture.path("raw", "reshade")
        reshade.mkdir(parents=True, exist_ok=True)
        trig_rows: list[list[int]] = []
        for new_idx, src_idx in enumerate(frames):
            t_ns, pair = matched[src_idx]
            color = read_image(pair.before)[..., :3]
            packed = sample_nearest(read_image(pair.after)[..., :3], new_w, new_h)
            small = cv2.resize(color, (new_w, new_h), interpolation=cv2.INTER_AREA)
            write_image(reshade / f"{new_idx:06d}{b_suf}.png", small)
            write_image(reshade / f"{new_idx:06d}{a_suf}.png", packed)
            trig_rows.append([new_idx, t_ns])
        _write_csv(fixture.path("raw", "triggers.csv"), ["frame_idx", "t_trigger_ns"], trig_rows)

        rows, raw_rows, header = read_pose_rows(session)
        times = [t for _, t in trig_rows]
        keep = [
            k
            for k, r in enumerate(rows)
            if any(abs(r["t_host_ns"] - t) <= POSE_WINDOW_NS for t in times)
        ]
        _write_csv(
            fixture.path("raw", "poses.csv"),
            header,
            [[raw_rows[k][h] for h in header] for k in keep],
        )
        _copy_calib(session, fixture, scale, new_w, new_h)
        _copy_hand_masks(session, fixture, frames, new_w, new_h)
        if palms is not None:
            n = _clip_palms(
                Path(palms), fixture.path("palms.geojson"), [rows[k] for k in keep], PALM_RADIUS_M
            )
            log.info("palms.geojson: %d palms within %.0f m", n, PALM_RADIUS_M)
        size = _dir_bytes(out)
        if size > max_bytes:
            raise ConfigError(f"fixture is {size} bytes, over the {max_bytes} byte limit")
    except BaseException:
        if not existed:
            shutil.rmtree(out, ignore_errors=True)
        raise
    return out


def _frames(value: str) -> tuple[int, ...]:
    try:
        return parse_drop(value)
    except ConfigError:
        raise argparse.ArgumentTypeError(f"expected comma-separated indices: {value!r}") from None


def register(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "fixture",
        help="write a downscaled raw sample session (under 5 MB) for tests",
        description="Build a small raw session from selected frames. --session is the source.",
    )
    add_standard_args(parser)
    parser.add_argument("--out", required=True, type=Path, metavar="DIR")
    parser.add_argument("--frames", required=True, type=_frames, metavar="I,J,...")
    parser.add_argument("--scale", type=float, default=0.25, metavar="X")
    parser.add_argument("--palms", type=Path, default=None, metavar="GEOJSON")
    parser.add_argument("--drop", type=_frames, default=(), metavar="I,J")
    parser.add_argument("--before-suffix", default=None, metavar="S")
    parser.add_argument("--after-suffix", default=None, metavar="S")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    session = session_from_args(args)
    out = build_fixture(
        session,
        args.out,
        args.frames,
        args.scale,
        palms=args.palms,
        drop=args.drop,
        before_suffix=args.before_suffix,
        after_suffix=args.after_suffix,
    )
    print(f"wrote fixture {out} ({_dir_bytes(out)} bytes)")
    return 0
