"""Shared Gemini Interactions API client: request building and response parsing.

Confirmed live against the real API on 2026-11-25: POST /v1beta/interactions,
with an Api-Revision header and the model named in the body, not the URL path.
A response's `steps` list mixes step types: "thought" steps carry an opaque
reasoning signature (no usable output), and "model_output" steps carry the
actual content blocks - each a {"type": "text", "text": ...} or a
{"type": "audio", "data": <base64>, "mime_type": "audio/wav"}. There is no
top-level `output_text` field in the raw REST response (that's an SDK
convenience, not present here), so output must be read from these blocks.
"""
from __future__ import annotations

import base64
import os
from typing import Any

from . import config
from .http import CallResult, call_with_model_fallback, request_with_retry


def _headers() -> dict[str, str]:
    return {
        "x-goog-api-key": os.environ["GEMINI_API_KEY"],
        "Content-Type": "application/json",
        "Api-Revision": config.GEMINI_API_REVISION,
    }


def call_interactions(model: str, body_extra: dict[str, Any], *, max_attempts: int = config.MAX_RETRY_ATTEMPTS) -> CallResult:
    body = {"model": model, **body_extra}
    return request_with_retry(
        "POST", f"{config.GEMINI_API_BASE}/interactions", headers=_headers(), json_body=body, max_attempts=max_attempts
    )


def model_output_blocks(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Content blocks from the response's model_output step(s); thought steps are skipped."""
    blocks: list[dict[str, Any]] = []
    for step in data.get("steps", []):
        if step.get("type") == "model_output":
            blocks.extend(step.get("content", []))
    return blocks


def extract_text(data: dict[str, Any]) -> str:
    return "".join(b.get("text", "") for b in model_output_blocks(data) if b.get("type") == "text")


def extract_audio(data: dict[str, Any]) -> tuple[bytes, str]:
    """(raw_bytes, mime_type) for the first audio content block, or (b"", "") if there isn't one."""
    for b in model_output_blocks(data):
        if b.get("type") == "audio" and b.get("data"):
            return base64.b64decode(b["data"]), b.get("mime_type", "")
    return b"", ""


def generate_text(models: list[str], prompt: str) -> tuple[str, CallResult, str]:
    """Returns (model_used, call_result, text)."""

    def call(model: str) -> CallResult:
        return call_interactions(model, {"input": prompt})

    model, result = call_with_model_fallback(models, call)
    return model, result, extract_text(result.response.json())


def generate_speech(
    models: list[str], text: str, voice: str = config.GEMINI_DEFAULT_VOICE
) -> tuple[str, CallResult, bytes, str]:
    """Returns (model_used, call_result, audio_bytes, mime_type)."""

    def call(model: str) -> CallResult:
        return call_interactions(model, {"input": text, "generation_config": {"speech_config": [{"voice": voice}]}})

    model, result = call_with_model_fallback(models, call)
    audio_bytes, mime_type = extract_audio(result.response.json())
    return model, result, audio_bytes, mime_type
