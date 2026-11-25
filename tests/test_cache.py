from pipeline.cache import stage_key


def test_same_inputs_same_key():
    inputs = {"prompt": "a cat", "seed": 1}
    assert stage_key("keyframes", inputs) == stage_key("keyframes", dict(inputs))


def test_different_inputs_different_key():
    a = stage_key("keyframes", {"prompt": "a cat", "seed": 1})
    b = stage_key("keyframes", {"prompt": "a dog", "seed": 1})
    assert a != b


def test_key_is_independent_of_dict_order():
    a = stage_key("music", {"a": 1, "b": 2})
    b = stage_key("music", {"b": 2, "a": 1})
    assert a == b


def test_changing_one_shot_does_not_affect_siblings():
    shots = {
        "s01": {"prompt": "cat", "seed": 1},
        "s02": {"prompt": "dog", "seed": 2},
    }
    keys_before = {sid: stage_key("keyframes", inp) for sid, inp in shots.items()}

    shots["s01"]["prompt"] = "cat wearing a hat"
    keys_after = {sid: stage_key("keyframes", inp) for sid, inp in shots.items()}

    assert keys_after["s01"] != keys_before["s01"]
    assert keys_after["s02"] == keys_before["s02"]
