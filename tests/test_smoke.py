from unittest.mock import MagicMock, patch

from pipeline import smoke


def _resp(status_code=200, json_data=None, content=b"", headers=None):
    m = MagicMock()
    m.status_code = status_code
    m.headers = headers or {}
    m.content = content
    if json_data is not None:
        m.json.return_value = json_data
    else:
        m.json.side_effect = ValueError("no json")
    m.text = str(json_data) if json_data is not None else content.decode("latin1")
    return m


def test_gemini_text_skipped_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = smoke.smoke_gemini_text()
    assert result.status == "skipped"
    assert "GEMINI_API_KEY" in result.detail


def test_gemini_text_ok(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    response_json = {
        "steps": [
            {"type": "thought", "signature": "opaque"},
            {"type": "model_output", "content": [{"type": "text", "text": "OK"}]},
        ],
        "model": "gemini-3.8-flash",
    }
    with patch("pipeline.http.requests.request", return_value=_resp(200, json_data=response_json)):
        result = smoke.smoke_gemini_text()
    assert result.status == "ok"
    assert result.model == "gemini-3.8-flash"
    assert "OK" in result.detail


def test_gemini_tts_ok_detects_wav_header(monkeypatch):
    import base64

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    audio_b64 = base64.b64encode(b"RIFF....WAVEfmt ").decode()
    response_json = {
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "audio", "data": audio_b64, "mime_type": "audio/wav"}],
            }
        ],
        "model": "gemini-3.8-flash-tts",
    }
    with patch("pipeline.http.requests.request", return_value=_resp(200, json_data=response_json)):
        result = smoke.smoke_gemini_tts()
    assert result.status == "ok"
    assert "starts_with_RIFF=True" in result.detail


def test_cloudflare_flux_skipped_without_keys(monkeypatch):
    monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    result = smoke.smoke_cloudflare_flux()
    assert result.status == "skipped"


def test_cloudflare_flux_ok(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CF_API_TOKEN", "tok")
    with patch(
        "pipeline.http.requests.request",
        return_value=_resp(200, json_data={"result": {"image": "YmFzZTY0"}}),
    ):
        result = smoke.smoke_cloudflare_flux()
    assert result.status == "ok"
    assert "has_image_field=True" in result.detail


def test_gemini_text_error_on_fatal_status(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "bad-key")
    with patch("pipeline.http.requests.request", return_value=_resp(401)):
        result = smoke.smoke_gemini_text()
    assert result.status == "error"


def test_run_all_returns_three_results(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    results = smoke.run_all()
    assert [r.provider for r in results] == ["gemini_text", "gemini_tts", "cloudflare_flux"]
    assert all(r.status == "skipped" for r in results)
