"""Project paths, model ids, and a tiny .env loader (no external dependency).

Model ids and the Gemini request shape below reflect what was confirmed against
live provider docs on 2026-11-25 (see FAILURES.md for anything that drifts from
this once the `smoke` stage hits the real API).
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
STORYBOARD_PATH = PROJECT_ROOT / "storyboard.json"
SCHEMA_PATH = PROJECT_ROOT / "schema" / "storyboard.schema.json"
RUNS_LOG_PATH = PROJECT_ROOT / "runs.jsonl"
TIMING_PATH = OUTPUTS_DIR / "timing.json"

ENV_KEYS = (
    "GEMINI_API_KEY",
    "CF_ACCOUNT_ID",
    "CF_API_TOKEN",
    "HF_TOKEN",
    "KAGGLE_USERNAME",
    "KAGGLE_KEY",
)


def load_env(path: Path = ENV_PATH) -> None:
    """Populate os.environ from a .env file without overwriting already-set variables."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env()


def get_env(key: str) -> str:
    """Fetch a required environment variable, raising a clear error if it's unset."""
    value = os.environ.get(key, "")
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key} (set it in .env)")
    return value


# --- Gemini API ---------------------------------------------------------
# Confirmed live against the real API on 2026-11-25 (see pipeline/gemini.py):
# the surface is the Interactions API, not the older generateContent shape.
# "gemini-3.7-flash" does not exist (the real prior-stable fallback is
# gemini-3.6-flash); "gemini-3.8-flash-lite" also does not exist (the API
# itself suggests gemini-3.1-flash-lite). gemini-3.8-flash returned sustained
# 503 "high demand" during testing - kept as primary since the model id itself
# is valid, with gemini-3.6-flash as a working fallback (see FAILURES.md).
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_API_REVISION = "2026-05-20"
GEMINI_TEXT_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash"]  # primary, fallback
GEMINI_TEXT_LITE_MODEL = "gemini-3.1-flash-lite"
GEMINI_TTS_MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts"]  # primary, fallback - both confirmed live
GEMINI_DEFAULT_VOICE = "Kore"

# --- Cloudflare Workers AI (keyframes) ----------------------------------
# flux-2-klein-4b supports reference-image conditioning (needed for character
# consistency) and has a much larger daily free allowance than the 9B variant.
# Exact model slug is re-verified in pipeline/keyframes.py when that stage is built.
CF_API_URL_TEMPLATE = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
CF_FLUX_PRIMARY_MODEL = "@cf/black-forest-labs/flux-2-klein"
CF_FLUX_FALLBACK_MODEL = "@cf/black-forest-labs/flux-1-schnell"

# --- Shared retry policy ------------------------------------------------
MAX_RETRY_ATTEMPTS = 3
