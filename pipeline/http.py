"""Shared HTTP layer: retries with backoff, Retry-After handling, and model fallback.

Retry policy: exponential backoff (with jitter) on 429/500/502/503/504 and network
errors, honouring a Retry-After header when the server sends one. A 404 means "this
model/endpoint doesn't exist" and is not retried - callers use
`call_with_model_fallback` to move on to the next model in a fallback list instead.
A 400/401/403 is fatal and stops immediately with a readable message, since retrying
a bad request or a bad key only burns quota.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable

import requests

RETRYABLE_STATUS = {429, 500, 502, 503, 504}
FATAL_STATUS = {400, 401, 403}


class HttpCallError(Exception):
    """Base error for a call that exhausted its retries or failed unexpectedly."""

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class FatalHttpError(HttpCallError):
    """Non-retryable client error: bad request, bad auth, or forbidden."""


class ModelUnavailableError(HttpCallError):
    """404: this model/endpoint doesn't exist. The caller should try the next model."""


@dataclass
class CallResult:
    response: requests.Response
    attempts: int
    latency_ms: float


def request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    data: Any = None,
    files: Any = None,
    timeout: float = 60.0,
    max_attempts: int = 3,
    backoff_base_s: float = 1.0,
    backoff_cap_s: float = 30.0,
) -> CallResult:
    started = time.monotonic()
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.request(
                method, url, headers=headers, json=json_body, data=data, files=files, timeout=timeout
            )
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt == max_attempts:
                raise HttpCallError(f"network error after {attempt} attempt(s): {exc}") from exc
            _sleep_backoff(attempt, backoff_base_s, backoff_cap_s, retry_after=None)
            continue

        if resp.status_code < 400:
            return CallResult(response=resp, attempts=attempt, latency_ms=(time.monotonic() - started) * 1000)

        if resp.status_code == 404:
            raise ModelUnavailableError(
                f"404 from {url}: model/endpoint not found", status_code=404, body=resp.text[:500]
            )

        if resp.status_code in FATAL_STATUS:
            raise FatalHttpError(
                f"{resp.status_code} from {url}: {resp.text[:500]}",
                status_code=resp.status_code,
                body=resp.text[:500],
            )

        if resp.status_code in RETRYABLE_STATUS:
            if attempt == max_attempts:
                raise HttpCallError(
                    f"{resp.status_code} from {url} after {attempt} attempt(s): {resp.text[:500]}",
                    status_code=resp.status_code,
                    body=resp.text[:500],
                )
            _sleep_backoff(
                attempt, backoff_base_s, backoff_cap_s, retry_after=_parse_retry_after(resp.headers.get("Retry-After"))
            )
            continue

        raise HttpCallError(
            f"unexpected status {resp.status_code} from {url}: {resp.text[:500]}",
            status_code=resp.status_code,
            body=resp.text[:500],
        )

    raise HttpCallError(f"exhausted retries calling {url}") from last_exc


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _sleep_backoff(attempt: int, base_s: float, cap_s: float, retry_after: float | None) -> None:
    if retry_after is not None:
        time.sleep(min(retry_after, cap_s))
        return
    delay = min(base_s * (2 ** (attempt - 1)), cap_s)
    delay += random.uniform(0, delay * 0.1)
    time.sleep(delay)


def call_with_model_fallback(
    models: list[str],
    call_fn: Callable[[str], CallResult],
) -> tuple[str, CallResult]:
    """Try each model in order.

    A 404 (ModelUnavailableError) moves to the next model, and so does any other
    HttpCallError that survives its own retries - in practice this is a model
    stuck returning 429/503 ("high demand") for the whole retry budget, which is
    unavailable in every way that matters here. A FatalHttpError (400/401/403)
    propagates immediately instead: a bad key or bad request fails the same way
    against every model, so trying the rest would only burn quota for nothing.
    """
    last_exc: Exception | None = None
    for model in models:
        try:
            return model, call_fn(model)
        except FatalHttpError:
            raise
        except HttpCallError as exc:
            last_exc = exc
            continue
    raise HttpCallError(f"all models unavailable: {models}; last error: {last_exc}") from last_exc
