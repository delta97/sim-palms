"""Shared palmfx fixtures: a small synthetic scene with exact ground truth (plan 08, A15).

All fixtures are session-scoped and deterministic. Treat them as read-only: image arrays are
flagged non-writable, and ``synth_session_dir`` is shared by every test in the run, so copy it
(``shutil.copytree``) before modifying anything.

- ``synth_scene``: ``SynthScene`` with five blobs and the default building occluder (blob 0 is
  partly hidden behind the building).
- ``synth_K``: 320x180 ``Intrinsics`` (vertical FOV 50 deg).
- ``synth_rows``: eight canonical pose rows, 30 fps equivalent, 30 m/s north at 50 m, pitch -10.
- ``synth_frame``: the first rendered ``SynthFrame``.
- ``synth_seq``: all eight rendered frames (``idx``, ``t_ns`` and ``pose_row`` set).
- ``synth_session_dir``: a raw fake session (``offset_ms`` 40, ``pitch_sign`` -1) readable by
  ``open_session``; ``SYNTH_SESSION_OFFSET_MS`` and ``SYNTH_SESSION_CONVENTIONS`` give the truth.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from palmfx.offline.camera import Intrinsics
from palmfx.offline.synth import (
    SynthFrame,
    SynthScene,
    default_intrinsics,
    render_sequence,
    trajectory,
    write_fake_session,
)

SYNTH_PALMS_ENU = [(6.0, -8.0), (-14.0, 10.0), (22.0, -25.0), (-30.0, -15.0), (10.0, 40.0)]
SYNTH_FPS = 30.0
SYNTH_SPEED_MPS = 30.0
SYNTH_SESSION_OFFSET_MS = 40.0
SYNTH_SESSION_CONVENTIONS = {"pitch_sign": -1.0}


@pytest.fixture(scope="session")
def synth_scene() -> SynthScene:
    return SynthScene(palms_enu=SYNTH_PALMS_ENU, seed=7)


@pytest.fixture(scope="session")
def synth_K() -> Intrinsics:
    return default_intrinsics()


@pytest.fixture(scope="session")
def synth_rows() -> list[dict[str, float]]:
    return trajectory(8, SYNTH_SPEED_MPS, 1000.0 / SYNTH_FPS)


@pytest.fixture(scope="session")
def synth_seq(
    synth_scene: SynthScene, synth_rows: list[dict[str, float]], synth_K: Intrinsics
) -> list[SynthFrame]:
    return render_sequence(synth_scene, synth_rows, synth_K)


@pytest.fixture(scope="session")
def synth_frame(synth_seq: list[SynthFrame]) -> SynthFrame:
    return synth_seq[0]


@pytest.fixture(scope="session")
def synth_session_dir(synth_scene: SynthScene, tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("synth") / "20260101-SYN-low-01"
    return write_fake_session(
        root,
        synth_scene,
        n_frames=8,
        offset_ms=SYNTH_SESSION_OFFSET_MS,
        conventions=SYNTH_SESSION_CONVENTIONS,
        fps=SYNTH_FPS,
        speed_mps=SYNTH_SPEED_MPS,
    )
