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
    "MAGICHOUR_API_KEY",
    "AGNES_API_KEY",
    "CLOUDINARY_CLOUD_NAME",
    "CLOUDINARY_UPLOAD_PRESET",
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
# gemini-3.8-flash-tts free tier: 10 requests/day (confirmed live via a 429 error
# naming the exact limit) - narration regenerations should be batched, not iterative.
GEMINI_DEFAULT_VOICE = "Charon"  # male voice; confirmed callable, not confirmed by ear - listen and swap if wrong

# --- Cloudflare Workers AI (keyframes) ----------------------------------
# Confirmed live on 2026-11-26: the real model slug is "flux-2-klein-4b" (not
# "flux-2-klein" - that 400s with "No route for that URI"). Cloudflare's own
# docs don't document this model's multipart body fields at all (schema just
# says `multipart: {body: object, contentType: string}`, no field names). An
# uploaded "image" field and a guessed "strength" field were both accepted
# with 200 OK but the output completely ignored them both times (wrong
# ethnicity, wrong clothing, wrong art style, unrelated setting) - unlike
# flux-1-schnell's strict schema (extra fields cause a 400), this endpoint
# appears to silently drop unrecognized fields rather than use them. So
# character consistency here comes from repeating character_sheet.description
# + style_block in every shot's prompt (see keyframes.py), not from real
# reference-image conditioning. See FAILURES.md.
CF_API_URL_TEMPLATE = "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
CF_FLUX_PRIMARY_MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
CF_FLUX_FALLBACK_MODEL = "@cf/black-forest-labs/flux-1-schnell"

# --- Magic Hour (hosted image-to-video) ---------------------------------
# An alternative to the Kaggle/Colab Wan 2.2 GPU path when free-tier 16GB
# VRAM can't fit ti2v-5B's real >=24GB need (both platforms confirmed live -
# see FAILURES.md). Confirmed by inspecting the installed magic_hour SDK
# directly (not just its docs): "wan-2.2" is a real selectable model value
# for image_to_video.generate(), hosted on Magic Hour's own infrastructure -
# no local GPU/VRAM needed. wan-2.2 on this API only accepts 3-10 or 15
# second clips (confirmed via its own /v1/image-to-video reference);
# magichour.py clamps to [3, 10] since no shot needs 15s. The first account
# tried ran out of starter credits after 3 shots (see FAILURES.md) - a new
# API key picks back up where that left off (resumable by file existence).
MAGICHOUR_MODEL = "wan-2.2"
MAGICHOUR_RESOLUTION = "480p"
MAGICHOUR_CREDITS_PER_SECOND = {"480p": 24, "720p": 48}  # wan-2.2 rates, confirmed live via docs.magichour.ai
MAGICHOUR_USD_PER_CREDIT = 0.0012  # Creator usage-based rate, confirmed live via docs.magichour.ai/billing
MAGICHOUR_MIN_SECONDS = 3
MAGICHOUR_MAX_SECONDS = 10

# --- Agnes AI (hosted image-to-video) -----------------------------------
# An alternative to the Kaggle/Colab Wan 2.2 GPU path when free-tier 16GB
# VRAM can't fit ti2v-5B's real >=24GB need (both platforms confirmed live -
# see FAILURES.md). Also previously tried Magic Hour's hosted wan-2.2 (see
# git history / FAILURES.md) - switched here when that account ran out of
# starter credits. Confirmed live against docs.agnes-ai.com: image-to-video
# is the "keyframe" mode of POST /v1/videos (not Wan 2.2 - Agnes's own
# models, "agnes-video-2.5" or "agnes-video-2.5-flash"). Flash is free during
# a current trial promotion (confirmed live: $0/second Angel User Trial
# Price) - that may change, check docs.agnes-ai.com/en/docs/pricing before
# assuming $0. "seconds" must be a string from "4" to "12" (confirmed live -
# no 3s minimum like Magic Hour had); agnes.py clamps to [4, 12].
#
# Real constraint: the API only accepts a publicly reachable image URL for
# `first_frame` (no upload/base64 field is documented) - agnes.py hosts each
# local keyframe via Cloudinary's unsigned upload API first, just long enough
# for Agnes to fetch it. These are stylized illustration stills of fictional
# characters (never the real reference photos - see ETHICS.md), so public
# exposure was judged an acceptable trade-off; flagged to the user before
# building this. (Tried first, both dead ends: Cloudflare R2 requires a
# payment method on file even for the free tier; catbox.moe/litterbox and
# 0x0.st have both locked down anonymous uploads due to AI-agent abuse,
# confirmed live via their own error responses - see FAILURES.md.)
AGNES_API_BASE = "https://apihub.agnes-ai.com/v1"
AGNES_API_STATUS_URL = "https://apihub.agnes-ai.com/agnesapi"
AGNES_MODEL = "agnes-video-2.5-flash"
AGNES_SIZE = "720P"  # required exact value for the flash model (confirmed live: any other value 400s)
# No aspect_ratio param here - keyframe mode rejects it outright (confirmed
# live: 400 "output follows the input image"), which is fine since our
# keyframes are already square.
AGNES_MIN_SECONDS = 4
AGNES_MAX_SECONDS = 12
AGNES_USD_PER_SECOND = 0.0  # confirmed live: flash trial price is $0/sec as of 2026-11-26 - re-check before assuming this still holds

# --- Cloudinary (unsigned image hosting, for Agnes AI's first_frame URL) ---
CLOUDINARY_UPLOAD_URL_TEMPLATE = "https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"

# --- Shared retry policy ------------------------------------------------
MAX_RETRY_ATTEMPTS = 3
