"""palmfx.offline.session: layout, frames.jsonl and mask I/O."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from palmcore.errors import ConfigError
from palmfx.offline.session import (
    MaskSet,
    new_session,
    open_session,
    read_image,
    read_mask,
    write_image,
    write_mask,
)


def test_new_and_open_round_trip(tmp_path: Path) -> None:
    root = tmp_path / "20261205-T1-low-01"
    made = new_session(root, {"site": "T1", "resolution": [8, 6]})
    for name in ("raw", "frames", "calib", "masks"):
        assert (root / name).is_dir()
    opened = open_session(root)
    assert opened.meta == made.meta
    assert opened.meta["session_id"] == "20261205-T1-low-01"
    assert opened.meta["site"] == "T1"
    assert opened.path("masks", "hand") == root / "masks" / "hand"
    assert opened.frames() == []


def test_new_session_keeps_given_id_and_refuses_overwrite(tmp_path: Path) -> None:
    new_session(tmp_path / "s", {"session_id": "custom"})
    assert open_session(tmp_path / "s").meta["session_id"] == "custom"
    with pytest.raises(ConfigError, match="already exists"):
        new_session(tmp_path / "s", {})


def test_open_session_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not a session"):
        open_session(tmp_path)
    (tmp_path / "session.json").write_text("{nope", encoding="utf-8")
    with pytest.raises(ConfigError, match="cannot read"):
        open_session(tmp_path)
    (tmp_path / "session.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ConfigError, match="JSON object"):
        open_session(tmp_path)


def test_frames_parsing(tmp_path: Path) -> None:
    s = new_session(tmp_path / "s", {})
    lines = [
        {
            "idx": 0,
            "t_ns": 1234567890,
            "color": "frames/000000.color.png",
            "depthraw": "frames/000000.depthraw.npy",
            "depth": "frames/000000.depth.npy",
            "pose": {"lat_deg": 32.7893, "heading_deg": 271.0},
            "pose_gap_ms": 4.1,
        },
        {"idx": 1, "t_ns": 5, "color": "frames/000001.color.png", "pose": None},
    ]
    text = "\n".join(json.dumps(x) for x in lines) + "\n\n"
    s.path("frames.jsonl").write_text(text, encoding="utf-8")
    first, second = s.frames()
    assert first.idx == 0
    assert first.t_ns == 1234567890
    assert first.color == s.root / "frames" / "000000.color.png"
    assert first.depthraw == s.root / "frames" / "000000.depthraw.npy"
    assert first.depth == s.root / "frames" / "000000.depth.npy"
    assert first.pose == {"lat_deg": 32.7893, "heading_deg": 271.0}
    assert first.pose_gap_ms == pytest.approx(4.1)
    assert second.depthraw is None
    assert second.depth is None
    assert second.pose is None
    assert second.pose_gap_ms is None


@pytest.mark.parametrize(
    "line",
    ["not json", '{"idx": 0}', '{"idx": 0, "t_ns": 1, "color": "c", "pose": 3}'],
)
def test_frames_bad_line(tmp_path: Path, line: str) -> None:
    s = new_session(tmp_path / "s", {})
    s.path("frames.jsonl").write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"frames\.jsonl:1"):
        s.frames()


def test_image_round_trip_is_rgb(tmp_path: Path) -> None:
    img = np.zeros((4, 5, 3), dtype=np.uint8)
    img[..., 0] = 200  # red in RGB order
    img[1, 2] = (1, 2, 3)
    write_image(tmp_path / "sub" / "c.png", img)
    back = read_image(tmp_path / "sub" / "c.png")
    assert back.dtype == np.uint8
    assert np.array_equal(back, img)
    rgba = np.dstack([img, np.full((4, 5), 9, dtype=np.uint8)])
    write_image(tmp_path / "a.png", rgba)
    assert np.array_equal(read_image(tmp_path / "a.png"), rgba)


def test_read_image_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="cannot read image"):
        read_image(tmp_path / "missing.png")
    (tmp_path / "bad.png").write_bytes(b"not a png")
    with pytest.raises(ConfigError, match="cannot decode"):
        read_image(tmp_path / "bad.png")


def _two_blob_mask() -> MaskSet:
    labels = np.zeros((10, 12), dtype=np.uint16)
    labels[1:4, 1:4] = 1
    labels[5:9, 6:11] = 40000  # needs 16 bits
    union = np.where(labels > 0, 255, 0).astype(np.uint8)
    instances = [
        {
            "k": 1,
            "palm_id": "sdc-000123",
            "bbox": [1, 1, 3, 3],
            "area_px": 9,
            "z_m": 84.2,
            "base_uv": [2.0, 3.0],
            "top_uv": None,
        },
        {
            "k": 40000,
            "palm_id": None,
            "bbox": [6, 5, 10, 8],
            "area_px": 20,
            "z_m": None,
            "base_uv": None,
            "top_uv": None,
        },
    ]
    return MaskSet(union, labels, instances, "project-depth", {"depth_test": True, "tol": 0.5})


def test_mask_round_trip_exact(tmp_path: Path) -> None:
    m = _two_blob_mask()
    write_mask(tmp_path / "project-depth", 7, m)
    for suffix in (".png", ".inst.png", ".json"):
        assert (tmp_path / "project-depth" / f"000007{suffix}").is_file()
    back = read_mask(tmp_path / "project-depth", 7)
    assert back.union.dtype == np.uint8
    assert back.labels.dtype == np.uint16
    assert np.array_equal(back.union, m.union)
    assert np.array_equal(back.labels, m.labels)
    assert back.instances == m.instances
    assert back.method == "project-depth"
    assert back.params == m.params


def test_write_mask_normalises_union_to_0_255(tmp_path: Path) -> None:
    labels = np.zeros((3, 3), dtype=np.uint16)
    union = np.zeros((3, 3), dtype=np.uint8)
    union[1, 1] = 1
    write_mask(tmp_path, 0, MaskSet(union, labels, [], "hand", {}))
    back = read_mask(tmp_path, 0)
    assert set(np.unique(back.union).tolist()) == {0, 255}


def test_read_mask_derives_instances_without_inst_png(tmp_path: Path) -> None:
    union = np.zeros((8, 9), dtype=np.uint8)
    union[0:2, 0:2] = 255  # blob A
    union[2, 2] = 255  # diagonal neighbour of A: same component (8-connected)
    union[5:8, 5:9] = 255  # blob B
    union[0, 8] = 255  # isolated pixel C
    write_image(tmp_path / "hand" / "000003.png", union)
    m = read_mask(tmp_path / "hand", 3)
    assert m.method == "hand"
    assert m.params == {}
    assert m.labels.dtype == np.uint16
    assert int(m.labels.max()) == 3
    assert np.array_equal(m.labels > 0, union > 0)
    assert {i["k"] for i in m.instances} == {1, 2, 3}
    assert sorted(i["area_px"] for i in m.instances) == [1, 5, 12]
    big = max(m.instances, key=lambda i: i["area_px"])
    assert big["bbox"] == [5, 5, 8, 7]
    assert big["palm_id"] is None
    assert big["z_m"] is None
    assert big["base_uv"] is None
    assert big["top_uv"] is None


def test_read_mask_uses_json_method_when_inst_missing(tmp_path: Path) -> None:
    union = np.zeros((4, 4), dtype=np.uint8)
    union[1, 1] = 255
    write_image(tmp_path / "000000.png", union)
    (tmp_path / "000000.json").write_text(
        json.dumps({"method": "hand", "params": {"who": "me"}, "instances": []}), encoding="utf-8"
    )
    m = read_mask(tmp_path, 0)
    assert (m.method, m.params) == ("hand", {"who": "me"})
    assert len(m.instances) == 1


def test_empty_mask_has_no_instances(tmp_path: Path) -> None:
    write_image(tmp_path / "000000.png", np.zeros((4, 4), dtype=np.uint8))
    m = read_mask(tmp_path, 0)
    assert m.instances == []
    assert not m.labels.any()


def test_read_mask_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="mask not found"):
        read_mask(tmp_path, 0)
    write_image(tmp_path / "000001.png", np.zeros((4, 4, 3), dtype=np.uint8))
    with pytest.raises(ConfigError, match="single-channel"):
        read_mask(tmp_path, 1)
    write_image(tmp_path / "000002.png", np.zeros((4, 4), dtype=np.uint8))
    write_image(tmp_path / "000002.inst.png", np.zeros((2, 2), dtype=np.uint16))
    with pytest.raises(ConfigError, match="does not match"):
        read_mask(tmp_path, 2)
    write_image(tmp_path / "000003.png", np.zeros((4, 4), dtype=np.uint8))
    (tmp_path / "000003.json").write_text("[1]", encoding="utf-8")
    with pytest.raises(ConfigError, match="JSON object"):
        read_mask(tmp_path, 3)
    (tmp_path / "000003.json").write_text("{bad", encoding="utf-8")
    with pytest.raises(ConfigError, match="cannot read"):
        read_mask(tmp_path, 3)


def test_write_mask_shape_mismatch(tmp_path: Path) -> None:
    bad = MaskSet(np.zeros((2, 2), np.uint8), np.zeros((3, 3), np.uint16))
    with pytest.raises(ConfigError, match="same shape"):
        write_mask(tmp_path, 0, bad)
