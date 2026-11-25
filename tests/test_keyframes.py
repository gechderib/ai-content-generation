import pytest

from pipeline import cache, config, keyframes
from pipeline.http import FatalHttpError, ModelUnavailableError

STORYBOARD = {
    "style_block": "warm hand-painted illustration",
    "character_sheet": {
        "description": "a small boy, yellow t-shirt",
        "supporting": [
            "the mother: an adult woman in a cream patterned shawl, shown only from behind",
            "the shop owner: an adult man in a dark waistcoat, shown only as a silhouette",
        ],
    },
}

SHOT = {
    "id": "s01",
    "image_prompt": "a street lined with boutiques",
}


class _R:
    latency_ms = 10.0


@pytest.fixture(autouse=True)
def isolate_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(config, "RUNS_LOG_PATH", tmp_path / "runs.jsonl")
    yield


def test_shot_prompt_combines_all_three_parts():
    prompt = keyframes.shot_prompt(SHOT, STORYBOARD)
    assert "a street lined with boutiques" in prompt


def test_shot_prompt_excludes_unmentioned_supporting_characters():
    # SHOT's image_prompt names neither the mother nor the shop owner.
    prompt = keyframes.shot_prompt(SHOT, STORYBOARD)
    assert "cream patterned shawl" not in prompt
    assert "dark waistcoat" not in prompt


def test_shot_prompt_includes_mother_when_shot_mentions_her():
    shot = {"id": "s03", "image_prompt": "the mother seen from behind facing the shop owner"}
    prompt = keyframes.shot_prompt(shot, STORYBOARD)
    assert "cream patterned shawl" in prompt
    assert "dark waistcoat" in prompt


def test_shot_prompt_includes_only_the_character_actually_mentioned():
    shot = {"id": "s06", "image_prompt": "the shop owner's raised open hands in a refusing gesture"}
    prompt = keyframes.shot_prompt(shot, STORYBOARD)
    assert "dark waistcoat" in prompt
    assert "cream patterned shawl" not in prompt
    assert "a small boy" in prompt
    assert "hand-painted" in prompt


def test_generate_shot_keyframe_tries_klein_first(monkeypatch):
    klein_calls = []
    schnell_calls = []

    def fake_klein(prompt):
        klein_calls.append(prompt)
        return b"klein-image", _R()

    def fake_schnell(prompt):
        schnell_calls.append(prompt)
        return b"schnell-image", _R()

    monkeypatch.setattr(keyframes.flux, "generate_image_klein", fake_klein)
    monkeypatch.setattr(keyframes.flux, "generate_image_schnell", fake_schnell)

    path = keyframes.generate_shot_keyframe(SHOT, STORYBOARD)

    assert path.read_bytes() == b"klein-image"
    assert len(klein_calls) == 1
    assert len(schnell_calls) == 0


def test_generate_shot_keyframe_falls_back_to_schnell_on_klein_failure(monkeypatch):
    def fake_klein(prompt):
        raise ModelUnavailableError("nope", status_code=404)

    def fake_schnell(prompt):
        return b"schnell-image", _R()

    monkeypatch.setattr(keyframes.flux, "generate_image_klein", fake_klein)
    monkeypatch.setattr(keyframes.flux, "generate_image_schnell", fake_schnell)

    path = keyframes.generate_shot_keyframe(SHOT, STORYBOARD)
    assert path.read_bytes() == b"schnell-image"


def test_generate_shot_keyframe_raises_if_both_models_fail(monkeypatch):
    def fake_klein(prompt):
        raise ModelUnavailableError("nope", status_code=404)

    def fake_schnell(prompt):
        raise FatalHttpError("bad key", status_code=401)

    monkeypatch.setattr(keyframes.flux, "generate_image_klein", fake_klein)
    monkeypatch.setattr(keyframes.flux, "generate_image_schnell", fake_schnell)

    with pytest.raises(FatalHttpError):
        keyframes.generate_shot_keyframe(SHOT, STORYBOARD)


def test_generate_shot_keyframe_caches(monkeypatch):
    calls = []

    def fake_klein(prompt):
        calls.append(prompt)
        return b"klein-image", _R()

    monkeypatch.setattr(keyframes.flux, "generate_image_klein", fake_klein)

    path1 = keyframes.generate_shot_keyframe(SHOT, STORYBOARD)
    path2 = keyframes.generate_shot_keyframe(SHOT, STORYBOARD)

    assert path1 == path2
    assert len(calls) == 1


def test_different_shots_get_different_cache_paths(monkeypatch):
    def fake_klein(prompt):
        return f"image-for-{prompt}".encode(), _R()

    monkeypatch.setattr(keyframes.flux, "generate_image_klein", fake_klein)

    other_shot = {"id": "s02", "image_prompt": "a close-up of hands"}
    path_a = keyframes.generate_shot_keyframe(SHOT, STORYBOARD)
    path_b = keyframes.generate_shot_keyframe(other_shot, STORYBOARD)

    assert path_a != path_b
    assert path_a.read_bytes() != path_b.read_bytes()
