"""Session directory layout, frame records and mask read/write (plan 08, "Session data formats").

A session lives in ``data/fx/<session_id>/``. Images go through OpenCV and are held in RGB order.
Depth buffers and metric depth are ``.npy`` files; this module only records their paths.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from palmcore.errors import ConfigError

SESSION_JSON = "session.json"
FRAMES_JSONL = "frames.jsonl"
SESSION_DIRS = ("raw", "frames", "calib", "masks")

# 8-connected neighbourhood for labelling hand-painted masks.
_EIGHT = np.ones((3, 3), dtype=bool)
_MAX_LABEL = np.iinfo(np.uint16).max


@dataclass(frozen=True)
class FrameRecord:
    """One line of ``frames.jsonl`` with paths resolved against the session root."""

    idx: int
    t_ns: int
    color: Path
    depthraw: Path | None = None
    depth: Path | None = None
    pose: dict[str, Any] | None = None
    pose_gap_ms: float | None = None


@dataclass
class MaskSet:
    """Union mask (uint8 0/255), instance labels (uint16, 0 = background) and instance records."""

    union: NDArray[np.uint8]
    labels: NDArray[np.uint16]
    instances: list[dict[str, Any]] = field(default_factory=list)
    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)


class Session:
    """An opened session: its root directory, ``session.json`` contents and frame list."""

    def __init__(self, root: Path, meta: dict[str, Any]) -> None:
        self.root = root
        self.meta = meta

    def path(self, *parts: str) -> Path:
        """A path under the session root."""
        return self.root.joinpath(*parts)

    def frames(self) -> list[FrameRecord]:
        """Frames listed in ``frames.jsonl`` (empty before ingest), in file order."""
        path = self.path(FRAMES_JSONL)
        if not path.is_file():
            return []
        records: list[FrameRecord] = []
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(self._record(json.loads(line)))
            except (ValueError, KeyError, TypeError) as exc:
                raise ConfigError(f"{path}:{lineno}: bad frame record ({exc!r})") from exc
        return records

    def _opt(self, rel: Any) -> Path | None:
        return None if rel is None else self.root / str(rel)

    def _record(self, obj: dict[str, Any]) -> FrameRecord:
        pose = obj.get("pose")
        if pose is not None and not isinstance(pose, dict):
            raise TypeError("pose must be an object or null")
        gap = obj.get("pose_gap_ms")
        return FrameRecord(
            idx=int(obj["idx"]),
            t_ns=int(obj["t_ns"]),
            color=self.root / str(obj["color"]),
            depthraw=self._opt(obj.get("depthraw")),
            depth=self._opt(obj.get("depth")),
            pose=pose,
            pose_gap_ms=None if gap is None else float(gap),
        )


def _write_json(path: Path, doc: Any) -> None:
    text = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def open_session(root: Path) -> Session:
    """Open an existing session directory."""
    root = Path(root)
    meta_path = root / SESSION_JSON
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"not a session directory (no {SESSION_JSON}): {root}") from None
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read {meta_path}: {exc}") from exc
    if not isinstance(meta, dict):
        raise ConfigError(f"{meta_path} must hold a JSON object")
    return Session(root, meta)


def new_session(root: Path, meta: dict[str, Any]) -> Session:
    """Create the session directory skeleton and write ``session.json``.

    ``session_id`` defaults to the directory name. Refuses to overwrite an existing session.
    """
    root = Path(root)
    if (root / SESSION_JSON).exists():
        raise ConfigError(f"session already exists: {root}")
    doc = dict(meta)
    doc.setdefault("session_id", root.name)
    for name in SESSION_DIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    _write_json(root / SESSION_JSON, doc)
    return Session(root, doc)


def read_image(path: Path) -> NDArray[Any]:
    """Read a PNG unchanged. Three-channel images are returned in RGB order."""
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError as exc:
        raise ConfigError(f"cannot read image {path}: {exc}") from exc
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ConfigError(f"cannot decode image {path}")
    if img.ndim == 3 and img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    elif img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
    return np.asarray(img)


def write_image(path: Path, img: NDArray[Any]) -> None:
    """Write a PNG. Three-channel images are taken as RGB."""
    if img.ndim == 3 and img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    elif img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ConfigError(f"cannot encode image for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buf.tobytes())


def _mask_stem(mask_dir: Path, idx: int) -> Path:
    return Path(mask_dir) / f"{idx:06d}"


def derive_instances(union: NDArray[np.uint8]) -> tuple[NDArray[np.uint16], list[dict[str, Any]]]:
    """Label the 8-connected components of ``union`` and describe each as an instance record."""
    labelled, count = ndimage.label(union > 0, structure=_EIGHT)
    if count > _MAX_LABEL:
        raise ConfigError(f"too many mask components for a 16-bit label image: {count}")
    labels = labelled.astype(np.uint16)
    instances: list[dict[str, Any]] = []
    for k, sl in enumerate(ndimage.find_objects(labelled), start=1):
        if sl is None:  # pragma: no cover - labels are contiguous
            continue
        ys, xs = sl
        instances.append(
            {
                "k": k,
                "palm_id": None,
                "bbox": [int(xs.start), int(ys.start), int(xs.stop - 1), int(ys.stop - 1)],
                "area_px": int(np.count_nonzero(labels[sl] == k)),
                "z_m": None,
                "base_uv": None,
                "top_uv": None,
            }
        )
    return labels, instances


def read_mask(mask_dir: Path, idx: int) -> MaskSet:
    """Read frame ``idx`` of a mask method directory.

    ``NNNNNN.inst.png`` and ``NNNNNN.json`` are optional (hand masks): without the label image the
    instances are derived from 8-connected components of the union mask.
    """
    stem = _mask_stem(mask_dir, idx)
    union_path = stem.with_suffix(".png")
    if not union_path.is_file():
        raise ConfigError(f"mask not found: {union_path}")
    union_raw = read_image(union_path)
    if union_raw.ndim != 2:
        raise ConfigError(f"{union_path} must be a single-channel image")
    union = np.where(union_raw > 0, 255, 0).astype(np.uint8)

    doc: dict[str, Any] = {}
    json_path = stem.with_suffix(".json")
    if json_path.is_file():
        try:
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigError(f"cannot read {json_path}: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ConfigError(f"{json_path} must hold a JSON object")
        doc = loaded
    method = str(doc.get("method", Path(mask_dir).name))
    params = dict(doc.get("params") or {})

    inst_path = Path(f"{stem}.inst.png")
    if inst_path.is_file():
        labels_raw = read_image(inst_path)
        if labels_raw.ndim != 2 or labels_raw.shape != union.shape:
            raise ConfigError(f"{inst_path} does not match the shape of {union_path}")
        return MaskSet(
            union=union,
            labels=labels_raw.astype(np.uint16),
            instances=list(doc.get("instances") or []),
            method=method,
            params=params,
        )
    labels, instances = derive_instances(union)
    return MaskSet(union=union, labels=labels, instances=instances, method=method, params=params)


def write_mask(mask_dir: Path, idx: int, m: MaskSet) -> None:
    """Write ``NNNNNN.png`` (0/255), ``NNNNNN.inst.png`` (uint16) and ``NNNNNN.json``."""
    if m.union.ndim != 2 or m.union.shape != m.labels.shape:
        raise ConfigError("mask union and labels must be 2-D arrays of the same shape")
    if m.labels.size and (int(m.labels.max()) > _MAX_LABEL or int(m.labels.min()) < 0):
        raise ConfigError("mask labels do not fit in 16 bits")
    stem = _mask_stem(mask_dir, idx)
    Path(mask_dir).mkdir(parents=True, exist_ok=True)
    write_image(stem.with_suffix(".png"), np.where(m.union > 0, 255, 0).astype(np.uint8))
    write_image(Path(f"{stem}.inst.png"), m.labels.astype(np.uint16))
    _write_json(
        stem.with_suffix(".json"),
        {"method": m.method, "params": m.params, "instances": m.instances},
    )
