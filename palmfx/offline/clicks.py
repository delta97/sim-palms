"""Manual correspondences: ``clicks.json`` storage and the click UI (plan 08, A6).

``calib/clicks.json`` is a list of objects::

    {"frame": 12, "palm_id": "sdc-000123", "part": "base", "uv": [u, v]}
    {"frame": 12, "world": [lat, lon, h], "uv": [u, v]}

``part`` is ``base`` or ``top``. ``uv`` is in image pixels, continuous coordinates with the
origin at the top-left corner of the top-left pixel (the convention of ``camera.project``;
matplotlib's ``imshow`` event coordinates already match it).

Everything except ``run_click_ui`` is pure Python and testable headless. ``run_click_ui`` needs a
display and imports matplotlib lazily. It saves after every click and resumes from an existing
file.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from palmcore.errors import ConfigError
from palmcore.log import get_logger
from palmfx.offline.camera import CameraPose, Intrinsics, LocalFrame, pose_from_simvars, project
from palmfx.offline.session import FrameRecord, Session, read_image

log = get_logger(__name__)

CLICKS_REL = ("calib", "clicks.json")
PARTS = ("base", "top")

Click = dict[str, Any]


def validate_click(click: Mapping[str, Any]) -> Click:
    """Check one click against the format above and return a normalised copy."""
    try:
        frame = int(click["frame"])
        uv = [float(click["uv"][0]), float(click["uv"][1])]
        if len(click["uv"]) != 2 or not all(np.isfinite(uv)):
            raise ValueError("uv must be two finite numbers")
        out: Click = {"frame": frame}
        if "world" in click:
            world = [float(x) for x in click["world"]]
            if len(world) != 3 or not all(np.isfinite(world)):
                raise ValueError("world must be [lat, lon, h]")
            out["world"] = world
        else:
            part = str(click["part"])
            if part not in PARTS:
                raise ValueError(f"part must be one of {PARTS}")
            out["palm_id"] = str(click["palm_id"])
            out["part"] = part
        out["uv"] = uv
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ConfigError(f"bad click {dict(click)!r}: {exc}") from exc
    return out


def default_clicks_path(session: Session) -> Path:
    return session.path(*CLICKS_REL)


def load_clicks(path: Path) -> list[Click]:
    """Read and validate ``clicks.json``; a missing file is an empty list."""
    path = Path(path)
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if not isinstance(doc, list):
        raise ConfigError(f"{path} must hold a JSON list")
    return [validate_click(c) for c in doc]


def save_clicks(path: Path, clicks: Sequence[Mapping[str, Any]]) -> None:
    """Write ``clicks.json`` atomically (temp file then replace)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps([validate_click(c) for c in clicks], indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


_PALM_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def parse_label(text: str, frame: int, uv: Sequence[float]) -> Click:
    """Turn the typed label into a click.

    ``"<palm_id> base"``, ``"<palm_id> top"`` or ``"w <lat> <lon> <h>"`` (free world point).
    """
    parts = text.split()
    try:
        if parts and parts[0].lower() == "w":
            if len(parts) != 4:
                raise ValueError("expected: w LAT LON H")
            return validate_click({"frame": frame, "uv": list(uv), "world": parts[1:]})
        if len(parts) != 2 or parts[1] not in PARTS or not _PALM_ID.match(parts[0]):
            raise ValueError("expected: PALM_ID base|top")
        return validate_click(
            {"frame": frame, "uv": list(uv), "palm_id": parts[0], "part": parts[1]}
        )
    except (ValueError, ConfigError) as exc:
        raise ConfigError(f"cannot parse label {text!r}: {exc}") from exc


class ClickBook:
    """Click list with undo, persisted to ``path`` after every change."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.clicks: list[Click] = load_clicks(self.path)

    def add(self, click: Mapping[str, Any]) -> None:
        self.clicks.append(validate_click(click))
        save_clicks(self.path, self.clicks)

    def undo(self, frame: int | None = None) -> Click | None:
        """Remove the latest click (of ``frame`` if given); returns it or None."""
        for i in range(len(self.clicks) - 1, -1, -1):
            if frame is None or self.clicks[i]["frame"] == frame:
                gone = self.clicks.pop(i)
                save_clicks(self.path, self.clicks)
                return gone
        return None

    def for_frame(self, frame: int) -> list[Click]:
        return [c for c in self.clicks if c["frame"] == frame]


def palm_record(palm: Mapping[str, Any]) -> dict[str, Any]:
    """Flat ``{palm_id, lat, lon, ground_elev_m, height_m}`` from a GeoJSON feature or flat dict."""
    if "properties" in palm:
        props = palm["properties"]
        lon, lat = palm["geometry"]["coordinates"][:2]
        out = dict(props)
        out["lon"], out["lat"] = lon, lat
        return out
    return dict(palm)


def load_palms(path: Path) -> list[dict[str, Any]]:
    """Flat palm records from a ``palms.geojson`` path."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        return [palm_record(f) for f in doc["features"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConfigError(f"cannot read palms from {path}: {exc}") from exc


def overlay_points(
    frame_rec: FrameRecord,
    palms: Sequence[Mapping[str, Any]],
    K: Intrinsics,
    session: Session,
    bias: Mapping[str, float] | None = None,
) -> list[tuple[str, str, float, float]]:
    """``(palm_id, part, u, v)`` for the palm bases and tops visible in the frame's image."""
    if frame_rec.pose is None or not palms:
        return []
    recs = [palm_record(p) for p in palms]
    origin = recs[0]
    frame = LocalFrame(origin["lat"], origin["lon"], float(origin.get("ground_elev_m") or 0.0))
    cam: CameraPose = pose_from_simvars(
        frame_rec.pose, frame, session.meta.get("cam_offset_body_m") or (0.0, 0.0, 0.0), None, bias
    )
    out: list[tuple[str, str, float, float]] = []
    for rec in recs:
        g = float(rec.get("ground_elev_m") or 0.0)
        h = float(rec.get("height_m") or 12.0)
        for part, up in (("base", g), ("top", g + h)):
            uv, z = project(frame.to_enu(rec["lat"], rec["lon"], up), cam, K)
            u, v = float(uv[0, 0]), float(uv[0, 1])
            if z[0] > 0 and 0 <= u < K.width and 0 <= v < K.height:
                out.append((str(rec["palm_id"]), part, u, v))
    return out


def run_click_ui(
    session: Session,
    frames: Sequence[int],
    palms: Sequence[Mapping[str, Any]],
    out_path: Path,
    vfov_deg: float = 60.0,
) -> list[Click]:
    """Interactive clicking (needs a display and matplotlib).

    Left click records a point and asks for its label on the terminal (``PALM_ID base|top`` or
    ``w LAT LON H``; empty input cancels). Keys: ``u`` undo, ``n`` next frame, ``q`` quit.
    The file is saved after every click and existing clicks are kept (resume).
    """
    import matplotlib.pyplot as plt  # lazy: optional GUI dependency

    book = ClickBook(out_path)
    records = {r.idx: r for r in session.frames()}
    missing = [f for f in frames if f not in records]
    if missing:
        raise ConfigError(f"frames not in frames.jsonl (run ingest first): {missing}")
    for idx in frames:
        rec = records[idx]
        img = read_image(rec.color)
        K = Intrinsics.from_vfov(img.shape[1], img.shape[0], vfov_deg)
        fig, ax = plt.subplots(figsize=(12, 7))
        ax.imshow(img)
        ax.set_title(f"frame {idx}: click, then type label | u undo | n next | q quit")
        for pid, part, u, v in overlay_points(rec, palms, K, session):
            ax.plot([u], [v], "c+" if part == "base" else "m+", ms=8)
            ax.annotate(f"{pid[-6:]} {part}", (u, v), color="yellow", fontsize=7)
        drawn: list[Any] = []

        def redraw(frame_idx: int = idx, axes: Any = ax, store: list[Any] = drawn) -> None:
            for artist in store:
                artist.remove()
            store.clear()
            for c in book.for_frame(frame_idx):
                (pt,) = axes.plot([c["uv"][0]], [c["uv"][1]], "rx", ms=10)
                store.append(pt)
            axes.figure.canvas.draw_idle()

        def on_click(
            event: Any, frame_idx: int = idx, axes: Any = ax, redraw: Any = redraw
        ) -> None:
            if event.button != 1 or event.inaxes is not axes or event.xdata is None:
                return
            try:
                text = input(
                    f"label for ({event.xdata:.1f}, {event.ydata:.1f}) [id base|top, w lat lon h]: "
                )
                if text.strip():
                    book.add(parse_label(text, frame_idx, (event.xdata, event.ydata)))
            except (ConfigError, EOFError) as exc:
                print(f"not recorded: {exc}")
            redraw()

        def on_key(event: Any, frame_idx: int = idx, redraw: Any = redraw) -> None:
            if event.key == "u":
                book.undo(frame_idx)
                redraw()
            elif event.key in ("n", "q"):
                plt.close(event.canvas.figure)

        fig.canvas.mpl_connect("button_press_event", on_click)
        fig.canvas.mpl_connect("key_press_event", on_key)
        redraw()
        plt.show()
    return book.clicks
