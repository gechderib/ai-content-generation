import json
from pathlib import Path

import pytest

from pipeline import cache, config, shots

STORYBOARD = {
    "style_block": "warm hand-painted illustration",
    "character_sheet": {"description": "a small boy, yellow t-shirt"},
    "shots": [{"id": "s01", "motion_prompt": "slow gentle push-in", "image_prompt": "a quiet street"}],
}
TIMING = {"shots": [{"id": "s01", "effective_duration_s": 7.0}]}


@pytest.fixture(autouse=True)
def isolate_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(config, "RUNS_LOG_PATH", tmp_path / "runs.jsonl")
    yield


def test_zoompan_filter_push_in_increases_zoom():
    f = shots._zoompan_filter("slow gentle push-in", frames=100)
    assert "zoom+0.0012" in f


def test_zoompan_filter_pull_back_decreases_zoom():
    f = shots._zoompan_filter("slow pull-back, soft light", frames=100)
    assert "zoom-0.0012" in f


def test_zoompan_filter_static_holds_still():
    f = shots._zoompan_filter("slight hand movement, camera static", frames=100)
    assert "z='1'" in f


def test_shot_duration_s_looks_up_by_id():
    assert shots.shot_duration_s("s01", TIMING) == 7.0


def test_shot_duration_s_raises_for_unknown_shot():
    with pytest.raises(KeyError):
        shots.shot_duration_s("s99", TIMING)


def test_generate_fallback_clip_requires_keyframe(tmp_path, monkeypatch):
    shot = STORYBOARD["shots"][0]
    with pytest.raises(FileNotFoundError):
        shots.generate_fallback_clip(shot, STORYBOARD, TIMING)


def test_generate_fallback_clip_caches(monkeypatch, tmp_path):
    shot = STORYBOARD["shots"][0]

    from pipeline.keyframes import keyframe_path

    kf = keyframe_path(shot, STORYBOARD)
    kf.parent.mkdir(parents=True, exist_ok=True)
    kf.write_bytes(b"fake-keyframe")

    calls = []

    def fake_run_ffmpeg(args):
        calls.append(args)
        Path(args[-1]).write_bytes(b"fake-clip")

    monkeypatch.setattr(shots, "run_ffmpeg", fake_run_ffmpeg)

    path1 = shots.generate_fallback_clip(shot, STORYBOARD, TIMING)
    assert len(calls) == 1
    path2 = shots.generate_fallback_clip(shot, STORYBOARD, TIMING)
    assert path1 == path2
    assert len(calls) == 1  # cached, no second ffmpeg call


def test_generate_fallback_clip_uses_shot_duration_in_ffmpeg_args(monkeypatch):
    shot = STORYBOARD["shots"][0]
    from pipeline.keyframes import keyframe_path

    kf = keyframe_path(shot, STORYBOARD)
    kf.parent.mkdir(parents=True, exist_ok=True)
    kf.write_bytes(b"fake-keyframe")

    captured = {}
    monkeypatch.setattr(shots, "run_ffmpeg", lambda args: captured.setdefault("args", args))

    shots.generate_fallback_clip(shot, STORYBOARD, TIMING)
    assert "7.0" in captured["args"]


def test_import_shot_clip_copies_and_logs_gpu_minutes(tmp_path):
    shot = STORYBOARD["shots"][0]
    import_dir = tmp_path / "kaggle_out"
    import_dir.mkdir()
    (import_dir / "s01.mp4").write_bytes(b"real-wan-clip")
    (import_dir / "gpu_log.json").write_text(json.dumps({"s01": {"gpu_minutes": 3.5}}))

    path = shots.import_shot_clip(shot, import_dir, {"s01": {"gpu_minutes": 3.5}})
    assert path.read_bytes() == b"real-wan-clip"


def test_import_shot_clip_raises_if_source_missing(tmp_path):
    shot = STORYBOARD["shots"][0]
    import_dir = tmp_path / "kaggle_out"
    import_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        shots.import_shot_clip(shot, import_dir, {})


def test_run_requires_fallback_or_import_dir():
    with pytest.raises(ValueError):
        shots.run()
