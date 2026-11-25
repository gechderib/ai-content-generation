"""smoke: one real call each to Gemini text, Gemini TTS, and Cloudflare Workers AI (FLUX).

This is where assumptions about each provider's request/response shape meet
reality. Every call's latency and raw response shape go to runs.jsonl. A
provider whose required env var(s) aren't set yet is reported as "skipped",
not an error, so this is useful to run before every key is filled in.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from . import config, gemini
from .http import HttpCallError, call_with_model_fallback, request_with_retry
from .runs_log import log_call


@dataclass
class SmokeResult:
    provider: str
    status: str  # "ok" | "error" | "skipped"
    model: str | None = None
    latency_ms: float | None = None
    detail: str = ""


def _missing_env(*keys: str) -> str | None:
    missing = [k for k in keys if not os.environ.get(k)]
    if missing:
        return f"missing env var(s): {', '.join(missing)} (set in .env)"
    return None


def smoke_gemini_text() -> SmokeResult:
    reason = _missing_env("GEMINI_API_KEY")
    if reason:
        return SmokeResult("gemini_text", "skipped", detail=reason)

    try:
        model, result, text = gemini.generate_text(config.GEMINI_TEXT_MODELS, "Reply with exactly one word: OK")
    except HttpCallError as exc:
        log_call(stage="smoke", shot_id=None, model=config.GEMINI_TEXT_MODELS[0], status="error", error=str(exc))
        return SmokeResult("gemini_text", "error", detail=str(exc))

    log_call(
        stage="smoke", shot_id=None, model=model, status="ok", latency_ms=result.latency_ms,
        params={"output_text": text},
    )
    return SmokeResult("gemini_text", "ok", model=model, latency_ms=result.latency_ms, detail=text[:160])


def smoke_gemini_tts() -> SmokeResult:
    reason = _missing_env("GEMINI_API_KEY")
    if reason:
        return SmokeResult("gemini_tts", "skipped", detail=reason)

    try:
        model, result, audio_bytes, mime_type = gemini.generate_speech(config.GEMINI_TTS_MODELS, "selam")
    except HttpCallError as exc:
        log_call(stage="smoke", shot_id=None, model=config.GEMINI_TTS_MODELS[0], status="error", error=str(exc))
        return SmokeResult("gemini_tts", "error", detail=str(exc))

    is_wav = audio_bytes[:4] == b"RIFF"
    log_call(
        stage="smoke", shot_id=None, model=model, status="ok", latency_ms=result.latency_ms,
        params={"mime_type": mime_type, "bytes": len(audio_bytes), "starts_with_RIFF": is_wav},
    )
    return SmokeResult(
        "gemini_tts", "ok", model=model, latency_ms=result.latency_ms,
        detail=f"{len(audio_bytes)} bytes, mime_type={mime_type}, starts_with_RIFF={is_wav}",
    )


def smoke_cloudflare_flux() -> SmokeResult:
    reason = _missing_env("CF_ACCOUNT_ID", "CF_API_TOKEN")
    if reason:
        return SmokeResult("cloudflare_flux", "skipped", detail=reason)

    # flux-1-schnell has a confirmed simple JSON-in/base64-out shape; flux-2-klein's
    # reference-conditioning (multipart) request is built properly in keyframes.py.
    models = [config.CF_FLUX_FALLBACK_MODEL]

    def call(model: str):
        url = config.CF_API_URL_TEMPLATE.format(account_id=os.environ["CF_ACCOUNT_ID"], model=model)
        headers = {"Authorization": f"Bearer {os.environ['CF_API_TOKEN']}", "Content-Type": "application/json"}
        body = {"prompt": "a single warm lightbulb, hand-painted illustration", "steps": 4}
        return request_with_retry("POST", url, headers=headers, json_body=body, max_attempts=config.MAX_RETRY_ATTEMPTS)

    try:
        model, result = call_with_model_fallback(models, call)
    except HttpCallError as exc:
        log_call(stage="smoke", shot_id=None, model=models[0], status="error", error=str(exc))
        return SmokeResult("cloudflare_flux", "error", detail=str(exc))

    data: Any = {}
    try:
        data = result.response.json()
    except ValueError:
        pass
    has_image = isinstance(data, dict) and bool(data.get("result", {}).get("image"))

    log_call(
        stage="smoke", shot_id=None, model=model, status="ok", latency_ms=result.latency_ms,
        params={"has_image_field": has_image},
    )
    return SmokeResult(
        "cloudflare_flux", "ok", model=model, latency_ms=result.latency_ms, detail=f"has_image_field={has_image}"
    )


def run_all() -> list[SmokeResult]:
    return [smoke_gemini_text(), smoke_gemini_tts(), smoke_cloudflare_flux()]
