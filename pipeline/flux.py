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

flux-2-klein-4b: confirmed live - a multipart/form-data body (any Content-Type
override breaks it; let requests set its own default). "prompt" alone works
(200, a real image back). Cloudflare's own docs don't name this model's body
fields at all. An uploaded "image" field and a guessed "strength" field were
both accepted with 200 OK but had no visible effect on the output (completely
different ethnicity/clothing/style/setting both times) - unlike schnell's
strict schema (extra fields 400), this endpoint silently drops fields it
doesn't recognize rather than erroring, so its apparent "success" there was
not evidence the fields worked. Reference-image conditioning is NOT used here
for that reason; see config.py and keyframes.py for the text-only fallback.
"""
from __future__ import annotations

import base64
import os

from . import config
from .http import CallResult, request_with_retry


def _url(model: str) -> str:
    return config.CF_API_URL_TEMPLATE.format(account_id=os.environ["CF_ACCOUNT_ID"], model=model)


def _json_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['CF_API_TOKEN']}", "Content-Type": "application/json"}


def _auth_header() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['CF_API_TOKEN']}"}


def generate_image_schnell(prompt: str, steps: int = 4) -> tuple[bytes, CallResult]:
    body = {"prompt": prompt, "steps": steps}
    result = request_with_retry(
        "POST", _url(config.CF_FLUX_FALLBACK_MODEL), headers=_json_headers(), json_body=body,
        max_attempts=config.MAX_RETRY_ATTEMPTS,
    )
    data = result.response.json()
    image_b64 = (data.get("result") or {}).get("image")
    if not image_b64:
        raise RuntimeError(f"flux-1-schnell returned no image field: {str(data)[:300]}")
    return base64.b64decode(image_b64), result


def generate_image_klein(prompt: str) -> tuple[bytes, CallResult]:
    """Plain prompt, no reference image (see module docstring for why)."""
    result = request_with_retry(
        "POST", _url(config.CF_FLUX_PRIMARY_MODEL), headers=_auth_header(), data={"prompt": prompt},
        max_attempts=config.MAX_RETRY_ATTEMPTS,
    )
    data = result.response.json()
    image_b64 = (data.get("result") or {}).get("image")
    if not image_b64:
        raise RuntimeError(f"flux-2-klein-4b returned no image field: {str(data)[:300]}")
    return base64.b64decode(image_b64), result
