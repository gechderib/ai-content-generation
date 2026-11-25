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
