"""keyframes stage: one image per shot.

Each shot's prompt is image_prompt + character_sheet.description +
style_block. Character/style consistency across shots comes from repeating
that fixed description and style block in every prompt, not from true
reference-image conditioning - checked live on 2026-11-26, Cloudflare's
flux-2-klein-4b endpoint silently ignores both an uploaded reference image
and a guessed "strength" field (200 OK, completely unrelated output both
times), so it can't be relied on for this. See config.py and FAILURES.md.

flux-2-klein-4b (plain prompt) is tried first; flux-1-schnell is the
fallback if klein's call fails for any reason.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import config, flux
from .cache import cache_path, is_cached, stage_key
from .http import CallResult, HttpCallError
from .runs_log import log_call
from .schema_validate import load_storyboard

STAGE = "keyframes"


def _mentions(image_prompt: str, supporting_entry: str) -> bool:
    """Does this shot's own prompt actually feature this supporting character?

    A supporting entry looks like "the mother: ...details...". We only pull in
    its detailed description (shawl, waistcoat, etc.) when the shot's prompt
    names that character - otherwise an insert/close-up shot that shouldn't
    show them risks the model drawing them in anyway just because they're
    mentioned in the prompt text.
    """
    label = supporting_entry.split(":", 1)[0].strip().lower()
    keyword = label[4:] if label.startswith("the ") else label  # "the mother" -> "mother"
    return keyword in image_prompt.lower()


def shot_prompt(shot: dict[str, Any], storyboard: dict[str, Any]) -> str:
    cs = storyboard["character_sheet"]
    image_prompt = shot["image_prompt"]
    parts = [image_prompt, cs["description"]]
    parts.extend(s for s in cs.get("supporting", []) if _mentions(image_prompt, s))
    parts.append(storyboard["style_block"])
    return ", ".join(parts)


def keyframe_inputs(shot: dict[str, Any], storyboard: dict[str, Any]) -> dict[str, Any]:
    return {
        "prompt": shot_prompt(shot, storyboard),
        "models": [config.CF_FLUX_PRIMARY_MODEL, config.CF_FLUX_FALLBACK_MODEL],
    }


def keyframe_path(shot: dict[str, Any], storyboard: dict[str, Any]) -> Path:
    key = stage_key(STAGE, keyframe_inputs(shot, storyboard))
    return cache_path(STAGE, shot["id"], key, "jpg")


def _generate(prompt: str) -> tuple[bytes, str, CallResult]:
    """Try the primary model; fall back to schnell on any failure."""
    try:
        image_bytes, result = flux.generate_image_klein(prompt)
        return image_bytes, config.CF_FLUX_PRIMARY_MODEL, result
    except HttpCallError:
        image_bytes, result = flux.generate_image_schnell(prompt)
        return image_bytes, config.CF_FLUX_FALLBACK_MODEL, result


def generate_shot_keyframe(shot: dict[str, Any], storyboard: dict[str, Any], *, force: bool = False) -> Path:
    shot_id = shot["id"]
    path = keyframe_path(shot, storyboard)

    if is_cached(path) and not force:
        print(f"[cached]      {shot_id} keyframe ({path.name})")
        return path

    prompt = shot_prompt(shot, storyboard)
    try:
        image_bytes, model, result = _generate(prompt)
    except HttpCallError as exc:
        log_call(stage=STAGE, shot_id=shot_id, model=config.CF_FLUX_PRIMARY_MODEL, status="error", error=str(exc))
        raise

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(image_bytes)
    log_call(
        stage=STAGE, shot_id=shot_id, model=model, status="ok", latency_ms=result.latency_ms,
        params={"prompt": prompt, "bytes": len(image_bytes)},
        cache_key=stage_key(STAGE, keyframe_inputs(shot, storyboard)), output_path=str(path),
    )
    print(f"[regenerated] {shot_id} keyframe ({path.name}, model={model})")
    return path


def run(
    storyboard_path: Path = config.STORYBOARD_PATH, *, shot_filter: str | None = None, force: bool = False
) -> list[Path]:
    storyboard = load_storyboard(storyboard_path)
    shots = storyboard["shots"]
    if shot_filter:
        shots = [s for s in shots if s["id"] == shot_filter]
        if not shots:
            raise ValueError(f"no shot with id {shot_filter!r}")

    return [generate_shot_keyframe(shot, storyboard, force=force) for shot in shots]
