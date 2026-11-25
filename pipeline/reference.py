"""reference stage: generate several character/style reference candidates and
let a human pick one as the "golden" reference image that every shot's
keyframe is later conditioned on (character_sheet.reference_image in
storyboard.json).

Plain text-to-image (flux-1-schnell) - there is nothing to condition on yet,
since this step is what produces the reference keyframes.py conditions on.

Cloudflare's flux-1-schnell endpoint has no seed control (confirmed live: a
"seed" field is rejected outright). Candidates are distinguished by a local
"variant" label used only for cache keys and filenames, not sent to the API;
getting several different options means making several separate calls and
relying on the model's own non-determinism, not a reproducible seed.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import config, flux
from .cache import cache_path, is_cached, stage_key
from .http import HttpCallError
from .runs_log import log_call
from .schema_validate import load_storyboard

STAGE = "reference"
DEFAULT_VARIANTS = (1, 2, 3, 4)


def reference_prompt(storyboard: dict[str, Any]) -> str:
    cs = storyboard["character_sheet"]
    return f"{cs['description']}, {storyboard['style_block']}"


def candidate_inputs(prompt: str, variant: int) -> dict[str, Any]:
    return {"prompt": prompt, "variant": variant, "model": config.CF_FLUX_FALLBACK_MODEL}


def candidate_path(prompt: str, variant: int) -> Path:
    # Cloudflare's flux-1-schnell returns JPEG bytes (confirmed by magic-byte
    # inspection), not PNG, despite docs implying "an image" generically.
    key = stage_key(STAGE, candidate_inputs(prompt, variant))
    return cache_path(STAGE, f"candidate_v{variant}", key, "jpg")


def generate_candidate(prompt: str, variant: int, *, force: bool = False) -> Path:
    path = candidate_path(prompt, variant)
    if is_cached(path) and not force:
        print(f"[cached]      variant {variant} ({path.name})")
        return path

    try:
        image_bytes, result = flux.generate_image_schnell(prompt)
    except HttpCallError as exc:
        log_call(
            stage=STAGE, shot_id=f"variant{variant}", model=config.CF_FLUX_FALLBACK_MODEL, status="error", error=str(exc)
        )
        raise

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)
    log_call(
        stage=STAGE, shot_id=f"variant{variant}", model=config.CF_FLUX_FALLBACK_MODEL, status="ok",
        latency_ms=result.latency_ms, params={"prompt": prompt, "variant": variant, "bytes": len(image_bytes)},
        cache_key=stage_key(STAGE, candidate_inputs(prompt, variant)), output_path=str(path),
    )
    print(f"[regenerated] variant {variant} ({path.name})")
    return path


def generate_candidates(
    storyboard_path: Path = config.STORYBOARD_PATH, variants: tuple[int, ...] = DEFAULT_VARIANTS, force: bool = False
) -> list[Path]:
    storyboard = load_storyboard(storyboard_path)
    prompt = reference_prompt(storyboard)
    return [generate_candidate(prompt, variant, force=force) for variant in variants]


def pick(variant: int, storyboard_path: Path = config.STORYBOARD_PATH) -> Path:
    """Copy the chosen candidate to character_sheet.reference_image's path."""
    storyboard = load_storyboard(storyboard_path)
    prompt = reference_prompt(storyboard)
    src = candidate_path(prompt, variant)
    if not src.exists():
        raise FileNotFoundError(f"no candidate for variant {variant} at {src} - run `python -m pipeline reference` first")
    dest = config.PROJECT_ROOT / storyboard["character_sheet"]["reference_image"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())
    return dest
