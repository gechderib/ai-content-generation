import json

from pipeline.runs_log import log_call


def test_log_call_appends_one_json_line(tmp_path):
    path = tmp_path / "runs.jsonl"

    log_call(stage="smoke", shot_id=None, model="gemini-3.8-flash", status="ok", latency_ms=123.4, path=path)
    log_call(stage="smoke", shot_id=None, model="gemini-3.8-flash", status="ok", latency_ms=55.0, path=path)

    lines = path.read_text().splitlines()
    assert len(lines) == 2
    record = json.loads(lines[0])
    assert record["stage"] == "smoke"
    assert record["model"] == "gemini-3.8-flash"
    assert record["status"] == "ok"
    assert record["latency_ms"] == 123.4


def test_log_call_redacts_secret_looking_params(tmp_path):
    path = tmp_path / "runs.jsonl"

    log_call(
        stage="smoke",
        shot_id=None,
        model="gemini-3.8-flash",
        params={"api_key": "super-secret", "prompt": "hello"},
        status="ok",
        path=path,
    )

    record = json.loads(path.read_text().splitlines()[0])
    assert record["params"]["api_key"] == "<redacted>"
    assert record["params"]["prompt"] == "hello"
