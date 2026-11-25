import json
from pathlib import Path

import pytest

from pipeline import cache, config, music

STORYBOARD = {"music": {"caption": "gentle warm acoustic score", "bpm": 80, "instrumental": True, "seed": 42}, "end_card": {"duration_s": 2.5}}
TIMING = {"total_effective_duration_s": 60.0}


@pytest.fixture(autouse=True)
def isolate_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(config, "RUNS_LOG_PATH", tmp_path / "runs.jsonl")
    yield


def test_total_duration_s_adds_end_card():
    assert music.total_duration_s(STORYBOARD, TIMING) == 62.5


def test_generate_fallback_bed_requires_timing_json(tmp_path):
    with pytest.raises(FileNotFoundError):
        music.generate_fallback_bed(storyboard_path=tmp_path / "nope.json", timing_path=tmp_path / "missing.json")


def test_generate_fallback_bed_caches(tmp_path, monkeypatch):
    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(json.dumps(STORYBOARD))
    timing_path = tmp_path / "timing.json"
    timing_path.write_text(json.dumps(TIMING))

    calls = []

    def fake_run_ffmpeg(args):
        calls.append(args)
        Path(args[-1]).write_bytes(b"fake-bed")

    monkeypatch.setattr(music, "run_ffmpeg", fake_run_ffmpeg)

    path1 = music.generate_fallback_bed(storyboard_path=storyboard_path, timing_path=timing_path)
    assert len(calls) == 1
    path2 = music.generate_fallback_bed(storyboard_path=storyboard_path, timing_path=timing_path)
    assert path1 == path2
    assert len(calls) == 1  # cached


def test_import_candidates_copies_all_cand_files(tmp_path):
    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(json.dumps(STORYBOARD))

    import_dir = tmp_path / "kaggle_out"
    import_dir.mkdir()
    (import_dir / "cand1.wav").write_bytes(b"candidate-one")
    (import_dir / "cand2.wav").write_bytes(b"candidate-two")
    (import_dir / "gpu_log.json").write_text(json.dumps({"cand1": {"gpu_minutes": 0.2}, "cand2": {"gpu_minutes": 0.2}}))

    paths = music.import_candidates(str(import_dir), storyboard_path=storyboard_path)
    assert len(paths) == 2
    assert {p.read_bytes() for p in paths} == {b"candidate-one", b"candidate-two"}


def test_import_candidates_raises_if_none_found(tmp_path):
    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(json.dumps(STORYBOARD))
    import_dir = tmp_path / "kaggle_out"
    import_dir.mkdir()

    with pytest.raises(FileNotFoundError):
        music.import_candidates(str(import_dir), storyboard_path=storyboard_path)


def test_run_requires_fallback_or_import_dir():
    with pytest.raises(ValueError):
        music.run()
