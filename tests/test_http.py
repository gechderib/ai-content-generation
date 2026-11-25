from unittest.mock import MagicMock, patch

import pytest

from pipeline.http import (
    FatalHttpError,
    HttpCallError,
    ModelUnavailableError,
    call_with_model_fallback,
    request_with_retry,
)


def _resp(status_code, text="", headers=None):
    m = MagicMock()
    m.status_code = status_code
    m.text = text
    m.headers = headers or {}
    return m


def test_succeeds_on_first_try():
    with patch("pipeline.http.requests.request", return_value=_resp(200)) as mock_req:
        result = request_with_retry("POST", "https://example.test", max_attempts=3)
        assert result.response.status_code == 200
        assert result.attempts == 1
        mock_req.assert_called_once()


def test_retries_transient_error_then_succeeds():
    responses = [_resp(503), _resp(200)]
    with patch("pipeline.http.requests.request", side_effect=responses), patch("pipeline.http.time.sleep"):
        result = request_with_retry("POST", "https://example.test", max_attempts=3)
        assert result.attempts == 2


def test_gives_up_after_max_attempts():
    with patch("pipeline.http.requests.request", return_value=_resp(500)), patch("pipeline.http.time.sleep"):
        with pytest.raises(HttpCallError):
            request_with_retry("POST", "https://example.test", max_attempts=2)


def test_fatal_error_does_not_retry():
    with patch("pipeline.http.requests.request", return_value=_resp(401)) as mock_req:
        with pytest.raises(FatalHttpError):
            request_with_retry("POST", "https://example.test", max_attempts=3)
        mock_req.assert_called_once()


def test_404_raises_model_unavailable():
    with patch("pipeline.http.requests.request", return_value=_resp(404)):
        with pytest.raises(ModelUnavailableError):
            request_with_retry("POST", "https://example.test", max_attempts=3)


def test_retry_after_header_is_honoured():
    responses = [_resp(429, headers={"Retry-After": "2"}), _resp(200)]
    with patch("pipeline.http.requests.request", side_effect=responses), patch("pipeline.http.time.sleep") as mock_sleep:
        request_with_retry("POST", "https://example.test", max_attempts=3)
        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] == 2.0


def test_network_error_retries_then_raises():
    import requests

    with patch("pipeline.http.requests.request", side_effect=requests.exceptions.ConnectionError("boom")), patch(
        "pipeline.http.time.sleep"
    ):
        with pytest.raises(HttpCallError):
            request_with_retry("POST", "https://example.test", max_attempts=2)


def test_call_with_model_fallback_skips_404():
    def call_fn(model):
        if model == "model-a":
            raise ModelUnavailableError("nope", status_code=404)
        return request_with_retry("POST", "https://example.test", max_attempts=1)

    with patch("pipeline.http.requests.request", return_value=_resp(200)):
        used_model, result = call_with_model_fallback(["model-a", "model-b"], call_fn)
        assert used_model == "model-b"
        assert result.response.status_code == 200


def test_call_with_model_fallback_raises_when_all_unavailable():
    def call_fn(model):
        raise ModelUnavailableError("nope", status_code=404)

    with pytest.raises(HttpCallError):
        call_with_model_fallback(["model-a", "model-b"], call_fn)


def test_call_with_model_fallback_moves_on_after_exhausted_retries():
    """A model stuck returning 503 for its whole retry budget is as unusable as a 404."""
    responses = [_resp(503), _resp(503), _resp(200)]
    with patch("pipeline.http.requests.request", side_effect=responses), patch("pipeline.http.time.sleep"):

        def call_fn(model):
            max_attempts = 2 if model == "model-a" else 1
            return request_with_retry("POST", "https://example.test", max_attempts=max_attempts)

        used_model, result = call_with_model_fallback(["model-a", "model-b"], call_fn)
        assert used_model == "model-b"
        assert result.response.status_code == 200


def test_call_with_model_fallback_does_not_move_on_after_fatal_error():
    """A fatal error (bad key/request) fails the same way for every model, so don't try the rest."""
    calls = []

    def call_fn(model):
        calls.append(model)
        raise FatalHttpError("bad key", status_code=401)

    with pytest.raises(FatalHttpError):
        call_with_model_fallback(["model-a", "model-b"], call_fn)
    assert calls == ["model-a"]
