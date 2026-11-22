"""palmfx.offline.depth: log24 round trip, sky handling, model fit."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from palmcore.errors import ConfigError
from palmfx.offline.depth import (
    DMIN,
    DepthModel,
    fit_depth_model,
    pack_log24,
    read_depth_png,
    to_metric,
    unpack_log24,
)
from palmfx.offline.session import write_image


def test_round_trip_relative_error() -> None:
    d = np.logspace(-7, 0, 200_000)
    out = unpack_log24(pack_log24(d))
    # DMIN itself packs to code 0 (sky); every other value must round-trip
    keep = d > DMIN * 1.0000001
    assert np.max(np.abs(out[keep] - d[keep]) / d[keep]) <= 2e-6


def test_endpoints_and_sky() -> None:
    packed = pack_log24(np.array([0.0, 1e-9, DMIN * 0.999, DMIN, 1.0, np.nan]))
    assert packed.dtype == np.uint8
    assert packed[:4].tolist() == [[0, 0, 0]] * 4
    assert packed[5].tolist() == [0, 0, 0]
    assert packed[4].tolist() == [255, 255, 255]
    out = unpack_log24(packed)
    assert np.all(out[[0, 1, 2, 3, 5]] == 0.0)
    assert out[4] == pytest.approx(1.0)


def test_byte_layout_matches_shader() -> None:
    rgb = np.array([[1, 2, 3]], dtype=np.uint8)
    v = 0x010203
    expect = np.exp(np.log(DMIN) + v / 16777215 * -np.log(DMIN))
    assert unpack_log24(rgb)[0] == pytest.approx(expect, rel=1e-12)
    d = np.logspace(-6.9, 0, 5000)
    p = pack_log24(d).astype(np.int64)
    codes = p[:, 0] * 65536 + p[:, 1] * 256 + p[:, 2]
    assert np.all(np.diff(codes) >= 0)


def test_rounding_is_floor_half_up() -> None:
    # Halfway between codes rounds up, as the shader's floor(x + 0.5) does (not banker's).
    for code in (1, 2, 100):
        d = np.exp(np.log(DMIN) + (code + 0.5 + 1e-6) / 16777215 * -np.log(DMIN))
        p = pack_log24(np.array([d])).astype(np.int64)[0]
        assert p[0] * 65536 + p[1] * 256 + p[2] == code + 1


def test_alpha_ignored_and_bad_shape() -> None:
    rgba = np.concatenate([pack_log24(np.array([0.5])), np.array([[255]], np.uint8)], axis=-1)
    assert unpack_log24(rgba)[0] == pytest.approx(0.5, rel=2e-6)
    with pytest.raises(ConfigError):
        unpack_log24(np.zeros((4, 2), np.uint8))


def test_png_round_trip(tmp_path: Path) -> None:
    rng = np.random.default_rng(1)
    d = np.exp(rng.uniform(np.log(1e-6), 0, (12, 16)))
    d[0, 0] = 0.0
    p = tmp_path / "d.png"
    write_image(p, pack_log24(d))
    out = read_depth_png(p)
    assert out[0, 0] == 0.0
    assert np.max(np.abs(out.ravel()[1:] - d.ravel()[1:]) / d.ravel()[1:]) <= 2e-6
    g = tmp_path / "g.png"
    write_image(g, np.zeros((4, 4), np.uint8))
    with pytest.raises(ConfigError):
        read_depth_png(g)


def test_fit_recovers_reversed_z_style() -> None:
    rng = np.random.default_rng(0)
    z = np.exp(rng.uniform(np.log(5.0), np.log(500.0), 5000))
    d = 0.1 / z * (1 + 1e-4 * rng.standard_normal(z.size))
    m = fit_depth_model(d, z)
    assert m.a == pytest.approx(0.1, rel=2e-3)
    assert abs(m.b) < 2e-4
    assert m.rms_rel < 5e-3


def test_fit_recovers_standard_z_style() -> None:
    # d = A + B/z with A = 1.002, B = -0.2 (d -> A at far); z = B / (d - A)
    z = np.linspace(2.0, 800.0, 3000)
    d = 1.002 - 0.2 / z
    m = fit_depth_model(d, z)
    assert m.a == pytest.approx(-0.2, rel=1e-6)
    assert m.b == pytest.approx(-1.002, rel=1e-6)
    assert m.rms_rel < 1e-6


def test_fit_skips_invalid_and_errors() -> None:
    z = np.array([10.0, 20.0, 40.0, np.nan, 30.0])
    d = np.array([0.01, 0.005, 0.0025, 0.1, 0.0])
    m = fit_depth_model(d, z)
    assert m.a == pytest.approx(0.1, rel=1e-9)
    with pytest.raises(ConfigError):
        fit_depth_model(np.array([0.1]), np.array([1.0]))
    with pytest.raises(ConfigError):
        fit_depth_model(np.array([0.1, 0.2]), np.array([1.0]))


def test_to_metric_nan_for_sky() -> None:
    m = DepthModel(a=0.1, b=0.0)
    z = to_metric(np.array([0.0, 0.01, 0.001]), m)
    assert np.isnan(z[0])
    assert z[1:].tolist() == pytest.approx([10.0, 100.0])
    assert np.isnan(to_metric(np.array([0.5]), DepthModel(a=0.1, b=-1.0))[0])
