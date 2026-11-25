import json
from pathlib import Path

import pytest

from pipeline import cache
from pipeline.radio import build_ffmpeg_args, build_radio_cut


def test_build_ffmpeg_args_structure():
    audio_paths = [Path("/tmp/a.wav"), Path("/tmp/b.wav")]
    durations = [5.0, 3.0]
    args = build_ffmpeg_args(audio_paths, durations, total_duration=10.5, output_path=Path("/tmp/out.mp4"))

    assert args.count("-i") == 4  # 2 narration wavs + sine bed + color video
    joined = " ".join(args)
    assert "apad=whole_dur=5.0" in joined
    assert "apad=whole_dur=3.0" in joined
    assert "concat=n=2:v=0:a=1[voice]" in joined
    assert "sine=frequency=220:duration=10.5" in joined
    assert "color=c=black:s=1080x1920:r=24:d=10.5" in joined
    assert "amix=inputs=2" in joined
    assert "-map" in args
    assert "3:v" in args  # video is the 4th input (index 3): a.wav, b.wav, sine, color
    assert args[-1] == str(Path("/tmp/out.mp4"))


def test_build_radio_cut_requires_timing_json(tmp_path):
    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(json.dumps({"end_card": {"duration_s": 2.0}, "shots": [{"id": "s01", "duration_s": 5}]}))

    with pytest.raises(FileNotFoundError):
        build_radio_cut(
            storyboard_path=storyboard_path,
            timing_path=tmp_path / "timing.json",
            output_path=tmp_path / "out.mp4",
        )


def test_build_radio_cut_requires_narration_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "OUTPUTS_DIR", tmp_path)

    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(
        json.dumps(
            {
                "end_card": {"duration_s": 2.0},
                "shots": [
                    {"id": "s01", "duration_s": 5, "narration": {"text": "hi", "tts_style": "calm", "voice": "Kore"}}
                ],
            }
        )
    )
    timing_path = tmp_path / "timing.json"
    timing_path.write_text(json.dumps({"shots": [{"id": "s01", "effective_duration_s": 5.0}]}))

    with pytest.raises(FileNotFoundError):
        build_radio_cut(storyboard_path=storyboard_path, timing_path=timing_path, output_path=tmp_path / "out.mp4")


def test_build_radio_cut_paces_on_narration_length_not_planned_duration(tmp_path, monkeypatch):
    """The radio cut has no visuals yet, so a shot's long planned screen time
    (duration_s / effective_duration_s) must not become a silent gap - pacing
    follows the narration's own length plus a short breathing pause instead.
    """
    monkeypatch.setattr(cache, "OUTPUTS_DIR", tmp_path)

    from pipeline import narration as narration_module

    shot = {"id": "s01", "duration_s": 100, "narration": {"text": "hi", "voice": "Charon"}}
    audio_path = narration_module.shot_audio_path(shot)
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    audio_path.write_bytes(b"fake")

    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(json.dumps({"end_card": {"duration_s": 2.0}, "shots": [shot]}))

    timing_path = tmp_path / "timing.json"
    timing_path.write_text(
        json.dumps(
            {"shots": [{"id": "s01", "planned_duration_s": 100.0, "narration_duration_s": 3.0, "effective_duration_s": 100.0}]}
        )
    )

    captured = {}
    monkeypatch.setattr("pipeline.radio.run_ffmpeg", lambda args: captured.setdefault("args", args))

    build_radio_cut(storyboard_path=storyboard_path, timing_path=timing_path, output_path=tmp_path / "out.mp4")

    joined = " ".join(captured["args"])
    assert "apad=whole_dur=3.4" in joined  # 3.0s narration + 0.4s gap
    assert "apad=whole_dur=100.0" not in joined
