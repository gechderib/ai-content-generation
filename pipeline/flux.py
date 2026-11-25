"""Shared Cloudflare Workers AI image client (FLUX models).

flux-1-schnell: confirmed live - plain JSON body {"prompt":..., "steps":...},
response JSON {"result": {"image": <base64 PNG>}}. Simple, reliable, no
reference-image conditioning - used for the reference stage's first
candidates, where there's nothing to condition on yet since this step is
what creates the reference image. Checked live: Cloudflare's endpoint
rejects a "seed" field outright (400, "Additional or unevaluated properties
'/seed' at '/' not allowed") - there is no seed control here, so repeat
calls are the only way to get variation, and that variation is not
reproducible by seed the way the model's own README might imply.

flux-2-klein's reference-image-conditioned request shape (used in
keyframes.py, once a golden reference exists to condition shots on) is
verified separately before first use there, not assumed here.
"""
from __future__ import annotations

import base64
import os

from . import config
from .http import CallResult, request_with_retry


def _url(model: str) -> str:
    return config.CF_API_URL_TEMPLATE.format(account_id=os.environ["CF_ACCOUNT_ID"], model=model)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['CF_API_TOKEN']}", "Content-Type": "application/json"}


def generate_image_schnell(prompt: str, steps: int = 4) -> tuple[bytes, CallResult]:
    body = {"prompt": prompt, "steps": steps}
    result = request_with_retry(
        "POST", _url(config.CF_FLUX_FALLBACK_MODEL), headers=_headers(), json_body=body,
        max_attempts=config.MAX_RETRY_ATTEMPTS,
    )
    data = result.response.json()
    image_b64 = (data.get("result") or {}).get("image")
    if not image_b64:
        raise RuntimeError(f"flux-1-schnell returned no image field: {str(data)[:300]}")
    return base64.b64decode(image_b64), result
