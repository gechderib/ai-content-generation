from pathlib import Path

import pytest

from pipeline import cache, config, narration

SHOT = {
    "id": "s01",
    "duration_s": 7,
    "narration": {"text": "selam", "tts_style": "calm, warm, slow", "voice": "Kore"},
}


class _FakeResult:
    def __init__(self, latency_ms: float):
        self.latency_ms = latency_ms


@pytest.fixture(autouse=True)
def isolate_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(config, "RUNS_LOG_PATH", tmp_path / "runs.jsonl")
    yield


def test_narration_inputs_includes_everything_that_affects_output():
    inputs = narration.narration_inputs(SHOT)
    assert inputs["text"] == "selam"
    assert inputs["voice"] == "Kore"
    assert inputs["tts_style"] == "calm, warm, slow"
    assert "models" in inputs


def test_generate_shot_narration_writes_file_and_caches(monkeypatch):
    calls = []

    def fake_generate_speech(models, text, voice="Kore"):
        calls.append((models, text, voice))
        return "gemini-3.8-flash-tts", _FakeResult(123.0), b"RIFFfakewavdata", "audio/wav"

    monkeypatch.setattr(narration.gemini, "generate_speech", fake_generate_speech)

    path1 = narration.generate_shot_narration(SHOT)
    assert path1.exists()
    assert path1.read_bytes() == b"RIFFfakewavdata"
    assert len(calls) == 1

    path2 = narration.generate_shot_narration(SHOT)
    assert path2 == path1
    assert len(calls) == 1  # cached - no second API call


def test_generate_shot_narration_force_regenerates(monkeypatch):
    call_count = {"n": 0}

    def fake_generate_speech(models, text, voice="Kore"):
        call_count["n"] += 1
        return "gemini-3.8-flash-tts", _FakeResult(1.0), b"RIFFdata", "audio/wav"

    monkeypatch.setattr(narration.gemini, "generate_speech", fake_generate_speech)
    narration.generate_shot_narration(SHOT)
    narration.generate_shot_narration(SHOT, force=True)
    assert call_count["n"] == 2


def test_generate_shot_narration_raises_on_empty_audio(monkeypatch):
    def fake_generate_speech(models, text, voice="Kore"):
        return "gemini-3.8-flash-tts", _FakeResult(1.0), b"", "audio/wav"

    monkeypatch.setattr(narration.gemini, "generate_speech", fake_generate_speech)
    with pytest.raises(RuntimeError):
        narration.generate_shot_narration(SHOT)


def test_build_timing_uses_whichever_duration_is_longer(monkeypatch):
    storyboard = {
        "shots": [
            {"id": "s01", "duration_s": 5},
            {"id": "s02", "duration_s": 10},
        ]
    }
    audio_paths = {"s01": Path("fake1.wav"), "s02": Path("fake2.wav")}
    durations = {"fake1.wav": 8.0, "fake2.wav": 3.0}

    monkeypatch.setattr(narration, "ffprobe_duration_s", lambda path: durations[path.name])

    timing = narration.build_timing(storyboard, audio_paths)
    by_id = {s["id"]: s for s in timing["shots"]}

    assert by_id["s01"]["effective_duration_s"] == pytest.approx(8.0 + narration.PAD_S)
    assert by_id["s02"]["effective_duration_s"] == 10.0  # narration (3s) shorter than planned (10s)


def test_build_timing_flags_out_of_range_total():
    storyboard = {"shots": [{"id": "s01", "duration_s": 500}]}
    timing = narration.build_timing(storyboard, {})
    assert timing["total_effective_duration_s"] == 500.0
    assert timing["in_60_90_range"] is False
