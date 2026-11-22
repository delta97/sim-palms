"""Inpainting backends and the tiled runner (plan 08, A10).

Backends take and return ``uint8`` RGB images and a ``uint8`` mask where non-zero marks the pixels
to replace. :func:`inpaint_tiled` runs a backend only on padded tiles around mask components and
pastes the result back inside the mask, so every other pixel stays bit-identical.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy import ndimage

from palmcore.errors import ConfigError
from palmcore.log import get_logger

log = get_logger(__name__)

MODELS_LOCK = Path(__file__).with_name("models.lock.json")
LAMA_KEY = "big-lama"
_EIGHT = np.ones((3, 3), dtype=bool)
_MULTIPLE = 8


class Inpainter(Protocol):
    """An inpainting backend."""

    name: str

    def inpaint(self, rgb: NDArray[np.uint8], mask: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """Return ``rgb`` with the non-zero ``mask`` pixels filled in."""
        ...


class TeleaInpainter:
    """OpenCV Telea inpainting: no weights, used as the baseline and in unit tests."""

    name = "telea"

    def __init__(self, radius: int = 5) -> None:
        self.radius = radius

    def inpaint(self, rgb: NDArray[np.uint8], mask: NDArray[np.uint8]) -> NDArray[np.uint8]:
        m = np.where(mask > 0, 255, 0).astype(np.uint8)
        out = cv2.inpaint(np.ascontiguousarray(rgb), m, float(self.radius), cv2.INPAINT_TELEA)
        return np.asarray(out, dtype=np.uint8)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_models_lock(path: Path = MODELS_LOCK) -> dict[str, Any]:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigError(f"cannot read model lock file {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise ConfigError(f"{path} must hold a JSON object")
    return doc


def check_weights(weights: Path, lock_path: Path, *, trust_unlisted: bool) -> None:
    """Verify ``weights`` against the recorded SHA-256 in the lock file."""
    weights = Path(weights)
    if not weights.is_file():
        raise ConfigError(
            f"LaMa weights not found: {weights} (source URL: models.lock.json, key {LAMA_KEY})"
        )
    entry = load_models_lock(lock_path).get(LAMA_KEY)
    expected = entry.get("sha256") if isinstance(entry, dict) else None
    actual = sha256_file(weights)
    if expected:
        if actual != expected:
            raise ConfigError(
                f"{weights} sha256 {actual} does not match models.lock.json ({expected})"
            )
    elif trust_unlisted:
        log.warning("no sha256 recorded for %s; file digest is %s", LAMA_KEY, actual)
    else:
        raise ConfigError(
            f"models.lock.json has no sha256 for {LAMA_KEY}; file digest is {actual}. "
            "Record it there, or pass --trust-weights once."
        )


class LamaInpainter:
    """LaMa ("big-lama") TorchScript export. Needs ``torch`` (extra ``fx-lama``) and the weights.

    Input convention (from the simple-lama-inpainting source, see ``models.lock.json``): RGB
    float32 in [0, 1], NCHW; mask 1 where pixels are to be filled; sides padded to a multiple of 8;
    output RGB in [0, 1].
    """

    name = "lama"

    def __init__(
        self,
        weights: Path,
        device: str = "cpu",
        *,
        lock_path: Path = MODELS_LOCK,
        trust_unlisted_checksum: bool = False,
    ) -> None:
        try:
            import torch  # type: ignore[import-not-found,unused-ignore]
        except ImportError as exc:
            raise ConfigError(
                "the lama backend needs torch: pip install -e '.[fx-lama]' "
                "(use --backend telea for the baseline)"
            ) from exc
        check_weights(weights, lock_path, trust_unlisted=trust_unlisted_checksum)
        if device == "cuda" and not torch.cuda.is_available():
            raise ConfigError("--device cuda requested but CUDA is not available")
        self._torch = torch
        self.device = device
        self._model = torch.jit.load(str(weights), map_location=device)
        self._model.eval()
        self._model.to(device)

    def inpaint(self, rgb: NDArray[np.uint8], mask: NDArray[np.uint8]) -> NDArray[np.uint8]:
        torch = self._torch
        h, w = rgb.shape[:2]
        ph, pw = -h % _MULTIPLE, -w % _MULTIPLE
        img = rgb.astype(np.float32).transpose(2, 0, 1) / 255.0
        msk = (mask > 0).astype(np.float32)[None]
        if ph or pw:
            pad = ((0, 0), (0, ph), (0, pw))
            img = np.pad(img, pad, mode="symmetric")
            msk = np.pad(msk, pad, mode="symmetric")
        t_img = torch.from_numpy(np.ascontiguousarray(img)).unsqueeze(0).to(self.device)
        t_msk = torch.from_numpy(np.ascontiguousarray(msk)).unsqueeze(0).to(self.device)
        t_msk = (t_msk > 0) * 1
        with torch.inference_mode():
            out = self._model(t_img, t_msk)
        arr = out[0].permute(1, 2, 0).detach().cpu().numpy()[:h, :w]
        return np.asarray(np.clip(arr * 255, 0, 255).astype(np.uint8))


@dataclass(frozen=True)
class Tile:
    """Half-open pixel box ``[x0, x1) x [y0, y1)``."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def w(self) -> int:
        return self.x1 - self.x0

    @property
    def h(self) -> int:
        return self.y1 - self.y0

    def overlaps(self, other: Tile) -> bool:
        return (
            self.x0 < other.x1 and other.x0 < self.x1 and self.y0 < other.y1 and other.y0 < self.y1
        )

    def union(self, other: Tile) -> Tile:
        return Tile(
            min(self.x0, other.x0),
            min(self.y0, other.y0),
            max(self.x1, other.x1),
            max(self.y1, other.y1),
        )


def _grow_axis(lo: int, hi: int, limit: int) -> tuple[int, int]:
    """Grow ``[lo, hi)`` to a multiple of 8 inside ``[0, limit)`` if possible (up first)."""
    extra = -(hi - lo) % _MULTIPLE
    take = min(extra, limit - hi)
    hi += take
    extra -= take
    lo -= min(extra, lo)
    return lo, hi


def _round_tile(t: Tile, width: int, height: int) -> Tile:
    x0, x1 = _grow_axis(t.x0, t.x1, width)
    y0, y1 = _grow_axis(t.y0, t.y1, height)
    return Tile(x0, y0, x1, y1)


def plan_tiles(mask: NDArray[np.uint8], pad: int = 48) -> list[Tile]:
    """Padded component boxes, merged while they overlap; sides multiples of 8 where possible.

    Order is deterministic (by box origin, top to bottom then left to right).
    """
    height, width = mask.shape[:2]
    labelled, _ = ndimage.label(mask > 0, structure=_EIGHT)
    tiles: list[Tile] = []
    for sl in ndimage.find_objects(labelled):
        if sl is None:  # pragma: no cover - labels are contiguous
            continue
        ys, xs = sl
        box = Tile(
            max(0, xs.start - pad),
            max(0, ys.start - pad),
            min(width, xs.stop + pad),
            min(height, ys.stop + pad),
        )
        tiles.append(_round_tile(box, width, height))
    changed = True
    while changed:
        changed = False
        for i in range(len(tiles)):
            for j in range(i + 1, len(tiles)):
                if tiles[i].overlaps(tiles[j]):
                    merged = _round_tile(tiles[i].union(tiles[j]), width, height)
                    tiles = [t for k, t in enumerate(tiles) if k not in (i, j)] + [merged]
                    changed = True
                    break
            if changed:
                break
    return sorted(tiles, key=lambda t: (t.y0, t.x0, t.y1, t.x1))


def _inpaint_tile(
    inpainter: Inpainter,
    rgb: NDArray[np.uint8],
    mask: NDArray[np.uint8],
    max_side: int,
) -> NDArray[np.uint8]:
    h, w = rgb.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return inpainter.inpaint(rgb, mask)
    scale = max_side / longest
    sw = max(_MULTIPLE, round(w * scale / _MULTIPLE) * _MULTIPLE)
    sh = max(_MULTIPLE, round(h * scale / _MULTIPLE) * _MULTIPLE)
    small = np.asarray(cv2.resize(rgb, (sw, sh), interpolation=cv2.INTER_AREA), dtype=np.uint8)
    small_mask = np.asarray(
        cv2.resize(mask, (sw, sh), interpolation=cv2.INTER_NEAREST), dtype=np.uint8
    )
    filled = inpainter.inpaint(small, small_mask)
    return np.asarray(cv2.resize(filled, (w, h), interpolation=cv2.INTER_LINEAR), dtype=np.uint8)


def inpaint_tiled(
    rgb: NDArray[np.uint8],
    mask: NDArray[np.uint8],
    inpainter: Inpainter,
    pad: int = 48,
    max_side: int = 1024,
    feather_px: int = 4,
    on_tile: Callable[[Tile, float], None] | None = None,
) -> NDArray[np.uint8]:
    """Inpaint ``mask`` (non-zero = fill) on padded tiles; pixels outside the mask are unchanged.

    Inside the mask the result is alpha-blended with
    ``alpha = min(1, 2 * gaussian(mask, feather_px / 2))``, which softens corners and thin tips
    without leaving a rim of original pixels along straight edges. ``on_tile(tile, seconds)`` is
    called once per tile.
    """
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ConfigError("inpaint_tiled needs a uint8 RGB image")
    if mask.shape != rgb.shape[:2]:
        raise ConfigError(f"mask shape {mask.shape} does not match image shape {rgb.shape[:2]}")
    binary = np.where(mask > 0, 255, 0).astype(np.uint8)
    out = rgb.copy()
    tiles = plan_tiles(binary, pad)
    if not tiles:
        return out
    inside = binary > 0
    if feather_px > 0:
        soft = cv2.GaussianBlur(
            inside.astype(np.float32),
            (0, 0),
            sigmaX=feather_px / 2.0,
            borderType=cv2.BORDER_REPLICATE,
        )
        alpha = np.minimum(1.0, 2.0 * soft) * inside
    else:
        alpha = inside.astype(np.float32)
    for tile in tiles:
        sl = (slice(tile.y0, tile.y1), slice(tile.x0, tile.x1))
        t0 = time.perf_counter()
        filled = _inpaint_tile(inpainter, np.asarray(rgb[sl], dtype=np.uint8), binary[sl], max_side)
        if on_tile is not None:
            on_tile(tile, time.perf_counter() - t0)
        a = alpha[sl][..., None]
        region = out[sl].astype(np.float32)
        blended = region + a * (filled.astype(np.float32) - region)
        out[sl] = np.where(inside[sl][..., None], np.rint(blended), region).astype(np.uint8)
    return out
