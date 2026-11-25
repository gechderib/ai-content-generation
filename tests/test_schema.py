import copy
import json
from pathlib import Path

from pipeline.schema_validate import load_schema, validate_storyboard

ROOT = Path(__file__).resolve().parent.parent
STORYBOARD = json.loads((ROOT / "storyboard.json").read_text())
SCHEMA = load_schema()


def test_starter_storyboard_is_valid():
    assert validate_storyboard(STORYBOARD, SCHEMA) == []


def test_missing_reason_is_rejected():
    sb = copy.deepcopy(STORYBOARD)
    del sb["shots"][0]["reason"]
    errors = validate_storyboard(sb, SCHEMA)
    assert any("reason" in e for e in errors)


def test_empty_reason_is_rejected():
    sb = copy.deepcopy(STORYBOARD)
    sb["shots"][0]["reason"] = ""
    errors = validate_storyboard(sb, SCHEMA)
    assert any("reason" in e for e in errors)


def test_too_many_shots_is_rejected():
    sb = copy.deepcopy(STORYBOARD)
    for i in range(3):
        shot = copy.deepcopy(sb["shots"][-1])
        shot["id"] = f"s{90 + i}"
        sb["shots"].append(shot)
    errors = validate_storyboard(sb, SCHEMA)
    assert any("shots" in e for e in errors)


def test_too_few_shots_is_rejected():
    sb = copy.deepcopy(STORYBOARD)
    sb["shots"] = sb["shots"][:3]
    errors = validate_storyboard(sb, SCHEMA)
    assert any("shots" in e for e in errors)


def test_bad_total_duration_is_rejected():
    sb = copy.deepcopy(STORYBOARD)
    for s in sb["shots"]:
        s["duration_s"] = 1
    errors = validate_storyboard(sb, SCHEMA)
    assert any("duration" in e for e in errors)


def test_duplicate_id_is_rejected():
    sb = copy.deepcopy(STORYBOARD)
    sb["shots"][1]["id"] = sb["shots"][0]["id"]
    errors = validate_storyboard(sb, SCHEMA)
    assert any("duplicate" in e for e in errors)


def test_unknown_top_level_field_is_rejected():
    sb = copy.deepcopy(STORYBOARD)
    sb["mystery_field"] = "surprise"
    errors = validate_storyboard(sb, SCHEMA)
    assert errors != []
