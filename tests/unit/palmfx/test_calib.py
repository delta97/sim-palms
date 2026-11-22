"""FX-009: calibration recovers known truths from a synthetic session."""

from __future__ import annotations

import csv
import dataclasses
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from palmcore.errors import ConfigError
from palmfx.offline.calib import (
    CalibResult,
    calibrate,
    load_depth_model,
    warnings_for,
    write_calib,
    write_metric_depth,
)
from palmfx.offline.camera import Intrinsics, LocalFrame, pose_from_simvars, project
from palmfx.offline.clicks import (
    ClickBook,
    load_clicks,
    load_palms,
    overlay_points,
    palm_record,
    parse_label,
    save_clicks,
    validate_click,
)
from palmfx.offline.ingest import ingest, read_pose_rows, read_triggers
from palmfx.offline.session import open_session
from palmfx.offline.synth import (
    SYNTH_FRAME,
    T0_NS,
    SynthScene,
    default_intrinsics,
    make_palms_geojson,
    render,
    write_fake_session,
)
from palmfx.offline.timing import interpolate_poses

TRUE_VFOV = 55.0
TRUE_OFFSET_MS = 40.0
TRUE_BIAS = {"d_heading_deg": 1.0, "d_pitch_deg": 0.0, "d_bank_deg": 0.0}
CLICK_FRAMES = (0, 2, 4, 6, 7)
PALMS_ENU = [(6.0, -8.0), (-14.0, 10.0), (22.0, -25.0), (-30.0, -15.0), (10.0, 40.0)]


def _maneuver(root: Path) -> None:
    """Replace the straight-and-level attitude in raw/poses.csv with a varying one.

    A constant-velocity, constant-attitude flight cannot separate a time offset from a forward
    camera offset (see the calib module docstring), so the synthetic flight changes attitude.
    Raw pitch carries the session's ``pitch_sign`` of -1.
    """
    path = root / "raw" / "poses.csv"
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        rows = list(reader)
    for row in rows:
        t = (int(row["t_host_ns"]) - T0_NS) / 1e9
        row["heading_true_deg"] = f"{40.0 * t:.6f}"
        row["pitch_deg"] = f"{-(-10.0 + 6.0 * np.sin(2 * np.pi * 2.0 * t)):.6f}"
        row["bank_deg"] = f"{15.0 * np.sin(2 * np.pi * 1.5 * t):.6f}"
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


class Truth:
    """A synthetic session whose clicks and depth come from the true camera."""

    def __init__(self, root: Path, noise_px: float = 1.0, offset_ms: float = TRUE_OFFSET_MS):
        self.scene = SynthScene(palms_enu=PALMS_ENU, box_size=(0.5, 0.5, 12.0), seed=3)
        self.K = default_intrinsics(vfov_deg=TRUE_VFOV)
        write_fake_session(
            root,
            self.scene,
            n_frames=8,
            offset_ms=offset_ms,
            conventions={"pitch_sign": -1.0},
            K=self.K,
        )
        _maneuver(root)
        self.session = open_session(root)
        ingest(self.session)
        self.session = open_session(root)
        self.palms = [palm_record(f) for f in make_palms_geojson(self.scene)["features"]]

        triggers = dict(read_triggers(self.session))
        rows, _, _ = read_pose_rows(self.session)
        t_ns = [round(triggers[i] + offset_ms * 1e6) for i in range(8)]
        poses = interpolate_poses(rows, t_ns, 50, {"pitch_sign": -1.0})
        frame = LocalFrame(SYNTH_FRAME.lat0, SYNTH_FRAME.lon0, SYNTH_FRAME.h0)
        rng = np.random.default_rng(11)
        self.clicks: list[dict[str, Any]] = []
        for i, pose in enumerate(poses):
            assert pose is not None
            cam = pose_from_simvars(pose, frame, (0.0, 0.0, 0.0), None, TRUE_BIAS)
            rendered = render(self.scene, cam, self.K)
            np.save(self.session.path("frames", f"{i:06d}.depthraw.npy"), rendered.depth_raw)
            if i not in CLICK_FRAMES:
                continue
            for p, rec in enumerate(self.palms):
                parts = ["base"] + (["top"] if p in (1, 2, 4) else [])
                for part in parts:
                    h = rec["ground_elev_m"] + (rec["height_m"] if part == "top" else 0.0)
                    enu = frame.to_enu(rec["lat"], rec["lon"], h)
                    uv, _ = project(enu, cam, self.K)
                    uv = uv[0] + rng.normal(0.0, noise_px, 2)
                    self.clicks.append(
                        {
                            "frame": i,
                            "palm_id": rec["palm_id"],
                            "part": part,
                            "uv": [float(uv[0]), float(uv[1])],
                        }
                    )


@pytest.fixture(scope="module")
def truth(tmp_path_factory: pytest.TempPathFactory) -> Truth:
    return Truth(tmp_path_factory.mktemp("calib") / "20260101-SYN-low-01")


@pytest.fixture(scope="module")
def result(truth: Truth) -> CalibResult:
    return calibrate(truth.session, truth.clicks, truth.palms)


def test_recovers_vfov_offset_bias_and_rms(result: CalibResult) -> None:
    assert abs(result.vfov_deg - TRUE_VFOV) < 0.5
    assert abs(result.offset_ms - TRUE_OFFSET_MS) <= 5.0
    assert abs(result.bias["d_heading_deg"] - TRUE_BIAS["d_heading_deg"]) < 0.2
    assert result.rms_px < 2.0


def test_recovers_depth_model(result: CalibResult) -> None:
    m = result.depth_model
    assert m is not None
    assert abs(m.a - 0.1) / 0.1 < 0.02  # synthetic depth_raw = 0.1 / z
    assert m.rms_rel < 0.05


def test_deterministic(truth: Truth, result: CalibResult) -> None:
    again = calibrate(truth.session, truth.clicks, truth.palms)
    assert again == result


def test_warnings_follow_scaled_targets(result: CalibResult) -> None:
    # The 8 px target is for 1440 p; at the synthetic 180 p it scales to 1 px, so a 1 px-noise
    # fit is flagged there and passes at full size.
    assert any("reprojection RMS" in w for w in warnings_for(result))
    assert warnings_for(dataclasses.replace(result, width=2560, height=1440)) == []
    assert any(
        "no depth model" in w for w in warnings_for(dataclasses.replace(result, depth_model=None))
    )


def test_write_files_and_metric_depth(truth: Truth, result: CalibResult, tmp_path: Path) -> None:
    root = tmp_path / "copy"
    shutil.copytree(truth.session.root, root)
    session = open_session(root)
    paths = write_calib(session, result)
    assert {p.name for p in paths} == {
        "intrinsics.json",
        "time_offset.json",
        "pose_bias.json",
        "depth_model.json",
    }
    intr = json.loads(session.path("calib", "intrinsics.json").read_text(encoding="utf-8"))
    assert set(intr) == {"width", "height", "fx", "fy", "cx", "cy", "vfov_deg", "rms_px"}
    off = json.loads(session.path("calib", "time_offset.json").read_text(encoding="utf-8"))
    assert off["offset_ms"] == result.offset_ms
    model = load_depth_model(session)
    n = write_metric_depth(session, model)
    assert n == 8
    for rec in open_session(root).frames():
        assert rec.depth is not None and rec.depth.is_file()
        z = np.load(rec.depth)
        assert z.shape == (180, 320) and z.dtype == np.float32
    # ingest with the fitted offset now reads calib/time_offset.json
    ingest(session)
    t0 = read_triggers(session)[0][1]
    assert open_session(root).frames()[0].t_ns == round(t0 + result.offset_ms * 1e6)


def test_unknown_palm_and_empty_clicks(truth: Truth) -> None:
    with pytest.raises(ConfigError, match="no clicks"):
        calibrate(truth.session, [], truth.palms)
    bad = [{"frame": 0, "palm_id": "nope-0000000000000000", "part": "base", "uv": [1, 2]}]
    with pytest.raises(ConfigError, match="unknown palm_id"):
        calibrate(truth.session, bad * 5, truth.palms)


def test_free_world_points_work(truth: Truth) -> None:
    rec = truth.palms[0]
    clicks = [
        {"frame": 0, "world": [rec["lat"], rec["lon"], rec["ground_elev_m"]], "uv": [100.0, 120.0]}
    ] * 5
    with pytest.raises(ConfigError):  # too few clicks for 7 parameters is rejected cleanly
        calibrate(truth.session, clicks[:1], truth.palms)


# --- clicks storage ---------------------------------------------------------------------------


def test_click_roundtrip_and_validation(tmp_path: Path) -> None:
    path = tmp_path / "calib" / "clicks.json"
    assert load_clicks(path) == []
    clicks = [
        {"frame": 12, "palm_id": "syn-0000000000000001", "part": "base", "uv": [1.5, 2.5]},
        {"frame": 12, "world": [32.79, -117.25, 14.0], "uv": [3, 4]},
    ]
    save_clicks(path, clicks)
    got = load_clicks(path)
    assert [c["frame"] for c in got] == [12, 12]
    assert got[1]["world"] == [32.79, -117.25, 14.0]
    for bad in (
        {"frame": 1, "palm_id": "a", "part": "middle", "uv": [1, 2]},
        {"frame": 1, "palm_id": "a", "part": "base", "uv": [1]},
        {"frame": 1, "world": [1, 2], "uv": [1, 2]},
        {"uv": [1, 2]},
    ):
        with pytest.raises(ConfigError):
            validate_click(bad)
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_clicks(path)


def test_parse_label() -> None:
    assert parse_label("syn-1 top", 3, (1.0, 2.0)) == {
        "frame": 3,
        "palm_id": "syn-1",
        "part": "top",
        "uv": [1.0, 2.0],
    }
    assert parse_label("w 32.7 -117.1 14", 3, (1, 2))["world"] == [32.7, -117.1, 14.0]
    for bad in ("", "syn-1", "syn-1 middle", "w 1 2", "w a b c"):
        with pytest.raises(ConfigError):
            parse_label(bad, 0, (0, 0))


def test_click_book_saves_each_click_resumes_and_undoes(tmp_path: Path) -> None:
    path = tmp_path / "clicks.json"
    book = ClickBook(path)
    book.add(parse_label("a-1 base", 0, (1, 1)))
    assert len(load_clicks(path)) == 1  # saved straight away
    book.add(parse_label("a-1 top", 0, (1, 0)))
    book.add(parse_label("a-2 base", 1, (5, 5)))
    resumed = ClickBook(path)
    assert len(resumed.clicks) == 3
    assert resumed.undo(frame=0) is not None  # latest click of frame 0 is a-1 top
    assert [c["part"] for c in resumed.for_frame(0)] == ["base"]
    assert len(load_clicks(path)) == 2
    assert resumed.undo(frame=9) is None


def test_overlay_points_and_palm_loading(truth: Truth, tmp_path: Path) -> None:
    rec = truth.session.frames()[0]
    pts = overlay_points(rec, truth.palms, Intrinsics.from_vfov(320, 180, TRUE_VFOV), truth.session)
    assert pts and {p[1] for p in pts} <= {"base", "top"}
    path = tmp_path / "palms.geojson"
    path.write_text(json.dumps(make_palms_geojson(truth.scene)), encoding="utf-8")
    loaded = load_palms(path)
    assert len(loaded) == 5 and "height_m" in loaded[0]
    with pytest.raises(ConfigError):
        load_palms(tmp_path / "missing.geojson")


# --- commands ---------------------------------------------------------------------------------


def test_calib_command_end_to_end(
    truth: Truth, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from palmfx.offline.cli import main

    root = tmp_path / "cmd"
    shutil.copytree(truth.session.root, root)
    save_clicks(root / "calib" / "clicks.json", truth.clicks)
    palms = tmp_path / "palms.geojson"
    palms.write_text(json.dumps(make_palms_geojson(truth.scene)), encoding="utf-8")
    assert main(["calib", "--session", str(root), "--palms", str(palms)]) == 0
    out = capsys.readouterr().out
    assert "reprojection RMS" in out and "metric depth for 8 of 8" in out
    for name in ("intrinsics", "time_offset", "pose_bias", "depth_model"):
        assert (root / "calib" / f"{name}.json").is_file()
    frames = open_session(root).frames()
    assert len(frames) == 8
    assert all(f.depth is not None and f.depth.is_file() for f in frames)


def test_calib_command_needs_clicks(truth: Truth, tmp_path: Path) -> None:
    from palmfx.offline.cli import main

    root = tmp_path / "noclicks"
    shutil.copytree(truth.session.root, root)
    palms = tmp_path / "palms.geojson"
    palms.write_text(json.dumps(make_palms_geojson(truth.scene)), encoding="utf-8")
    assert main(["calib", "--session", str(root), "--palms", str(palms)]) != 0


def test_clicks_command_parses_and_rejects_bad_frames() -> None:
    from palmfx.offline.cli import build_parser

    args = build_parser().parse_args(
        ["clicks", "--session", "x", "--frames", "0,15,30", "--palms", "p.geojson"]
    )
    assert args.frames == (0, 15, 30)
    with pytest.raises(SystemExit):
        build_parser().parse_args(["clicks", "--session", "x", "--frames", "a", "--palms", "p"])
