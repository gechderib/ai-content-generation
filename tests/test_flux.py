import base64
from unittest.mock import MagicMock, patch

import pytest

from pipeline import flux
from pipeline.http import FatalHttpError


def _resp(status_code=200, json_data=None, text=""):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data if json_data is not None else {}
    m.text = text or str(json_data)
    return m


def test_generate_image_schnell_decodes_base64(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CF_API_TOKEN", "tok")
    raw = b"fake-png-bytes"
    encoded = base64.b64encode(raw).decode()

    with patch("pipeline.http.requests.request", return_value=_resp(200, {"result": {"image": encoded}})):
        image_bytes, result = flux.generate_image_schnell("a cat")

    assert image_bytes == raw
    assert result.response.status_code == 200


def test_generate_image_schnell_raises_on_missing_image_field(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CF_API_TOKEN", "tok")

    with patch("pipeline.http.requests.request", return_value=_resp(200, {"result": {}})):
        with pytest.raises(RuntimeError):
            flux.generate_image_schnell("a cat")


def test_generate_image_schnell_propagates_fatal_errors(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CF_API_TOKEN", "bad-tok")

    with patch("pipeline.http.requests.request", return_value=_resp(401, text="unauthorized")):
        with pytest.raises(FatalHttpError):
            flux.generate_image_schnell("a cat")


def test_generate_image_schnell_never_sends_a_seed_field(monkeypatch):
    # Cloudflare's endpoint rejects a "seed" field outright (strict schema,
    # confirmed live) - make sure we never regress and send one.
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CF_API_TOKEN", "tok")
    encoded = base64.b64encode(b"x").decode()

    with patch("pipeline.http.requests.request", return_value=_resp(200, {"result": {"image": encoded}})) as mock_req:
        flux.generate_image_schnell("a cat")

    sent_body = mock_req.call_args.kwargs["json"]
    assert "seed" not in sent_body
