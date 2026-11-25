import json

import pytest

from pipeline import cache, config, reference

STORYBOARD = {
    "style_block": "warm hand-painted illustration",
    "character_sheet": {
        "description": "a small boy, yellow t-shirt",
        "reference_image": "outputs/reference/golden.jpg",
    },
}


class _R:
    latency_ms = 10.0


@pytest.fixture(autouse=True)
def isolate_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "OUTPUTS_DIR", tmp_path)
    monkeypatch.setattr(config, "RUNS_LOG_PATH", tmp_path / "runs.jsonl")
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    yield


def test_reference_prompt_combines_description_and_style():
    prompt = reference.reference_prompt(STORYBOARD)
    assert "small boy" in prompt
    assert "hand-painted" in prompt


def test_generate_candidate_writes_file_and_caches(monkeypatch):
    calls = []

    def fake_generate_image_schnell(prompt, steps=4):
        calls.append(prompt)
        return b"fake-image-bytes", _R()

    monkeypatch.setattr(reference.flux, "generate_image_schnell", fake_generate_image_schnell)

    path1 = reference.generate_candidate("a boy", variant=1)
    assert path1.exists()
    assert path1.read_bytes() == b"fake-image-bytes"
    assert len(calls) == 1

    path2 = reference.generate_candidate("a boy", variant=1)
    assert path2 == path1
    assert len(calls) == 1  # cached, no second call


def test_different_variants_produce_different_cache_paths(monkeypatch):
    # No seed control on Cloudflare's endpoint (confirmed live) - each call is
    # expected to return different bytes just from the model's own
    # non-determinism; "variant" only distinguishes cache paths/filenames.
    counter = {"n": 0}

    def fake_generate_image_schnell(prompt, steps=4):
        counter["n"] += 1
        return f"image-{counter['n']}".encode(), _R()

    monkeypatch.setattr(reference.flux, "generate_image_schnell", fake_generate_image_schnell)

    path_a = reference.generate_candidate("a boy", variant=1)
    path_b = reference.generate_candidate("a boy", variant=2)
    assert path_a != path_b
    assert path_a.read_bytes() != path_b.read_bytes()


def test_pick_copies_chosen_candidate_to_golden_path(tmp_path, monkeypatch):
    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(json.dumps(STORYBOARD))

    def fake_generate_image_schnell(prompt, steps=4):
        return b"chosen-one", _R()

    monkeypatch.setattr(reference.flux, "generate_image_schnell", fake_generate_image_schnell)
    reference.generate_candidate(reference.reference_prompt(STORYBOARD), variant=3)

    dest = reference.pick(3, storyboard_path=storyboard_path)
    assert dest == tmp_path / "outputs" / "reference" / "golden.jpg"
    assert dest.read_bytes() == b"chosen-one"


def test_pick_raises_for_unknown_variant(tmp_path):
    storyboard_path = tmp_path / "storyboard.json"
    storyboard_path.write_text(json.dumps(STORYBOARD))

    with pytest.raises(FileNotFoundError):
        reference.pick(999, storyboard_path=storyboard_path)
