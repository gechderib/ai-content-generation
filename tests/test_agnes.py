import pytest

from pipeline import agnes


def test_clamp_duration_floors_to_minimum():
    assert agnes.clamp_duration(1.5) == 4


def test_clamp_duration_ceils_to_maximum():
    assert agnes.clamp_duration(20.0) == 12


def test_clamp_duration_rounds_within_range():
    assert agnes.clamp_duration(5.6) == 6


def test_shot_target_duration_s_uses_narration_plus_pad():
    shot = {"id": "s01", "duration_s": 7}
    timing_by_id = {"s01": {"narration_duration_s": 5.25, "effective_duration_s": 7.0}}
    # 5.25 + SHOT_PAD_S (0.4) = 5.65 -> rounds to 6
    assert agnes.shot_target_duration_s(shot, timing_by_id) == 6


def test_shot_target_duration_s_falls_back_to_effective_duration():
    shot = {"id": "s02", "duration_s": 6}
    timing_by_id = {"s02": {"narration_duration_s": None, "effective_duration_s": 6.0}}
    assert agnes.shot_target_duration_s(shot, timing_by_id) == 6


def test_run_requires_timing_json(tmp_path):
    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text('{"shots": []}')
    with pytest.raises(FileNotFoundError):
        agnes.run(storyboard_path=storyboard_path, timing_path=tmp_path / "missing.json")
