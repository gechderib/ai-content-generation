"""narration stage: one WAV per shot via Gemini TTS, cached by shot inputs.

Also writes outputs/timing.json: each shot's effective duration is
max(storyboard duration_s, narration audio duration + a small pad), since the
narration is what actually sets how long a shot needs to hold, not the
planning estimate in storyboard.json. storyboard.json itself is never
mutated - timing.json is the generated, narration-driven source of truth
the later shots/assemble stages read.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config, gemini
from .cache import cache_path, is_cached, stage_key
from .ffmpeg_utils import ffprobe_duration_s
from .http import HttpCallError
from .runs_log import log_call
from .schema_validate import load_storyboard

PAD_S = 0.3
STAGE = "narration"


def _tts_input(shot: dict[str, Any]) -> str:
    style = shot["narration"].get("tts_style", "").strip()
    text = shot["narration"]["text"]
    return f"Say {style}: {text}" if style else text


def narration_inputs(shot: dict[str, Any]) -> dict[str, Any]:
    """Everything that determines this shot's narration output - the cache key's basis."""
    return {
        "text": shot["narration"]["text"],
        "tts_style": shot["narration"].get("tts_style", ""),
        "voice": shot["narration"]["voice"],
        "models": config.GEMINI_TTS_MODELS,
    }


def shot_audio_path(shot: dict[str, Any]) -> Path:
    key = stage_key(STAGE, narration_inputs(shot))
    return cache_path(STAGE, shot["id"], key, "wav")


def generate_shot_narration(shot: dict[str, Any], *, force: bool = False) -> Path:
    shot_id = shot["id"]
    path = shot_audio_path(shot)

    if is_cached(path) and not force:
        print(f"[cached]      {shot_id} narration ({path.name})")
        return path

    voice = shot["narration"]["voice"]
    text = _tts_input(shot)
    try:
        model, result, audio_bytes, mime_type = gemini.generate_speech(config.GEMINI_TTS_MODELS, text, voice=voice)
    except HttpCallError as exc:
        log_call(stage=STAGE, shot_id=shot_id, model=config.GEMINI_TTS_MODELS[0], status="error", error=str(exc))
        raise

    if not audio_bytes:
        raise RuntimeError(f"{shot_id}: Gemini TTS returned no audio content (mime_type={mime_type!r})")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(audio_bytes)

    log_call(
        stage=STAGE, shot_id=shot_id, model=model, status="ok", latency_ms=result.latency_ms,
        params={"voice": voice, "mime_type": mime_type, "bytes": len(audio_bytes)},
        cache_key=stage_key(STAGE, narration_inputs(shot)), output_path=str(path),
    )
    print(f"[regenerated] {shot_id} narration ({path.name})")
    return path


def build_timing(storyboard: dict[str, Any], audio_paths: dict[str, Path]) -> dict[str, Any]:
    entries = []
    total = 0.0
    for shot in storyboard["shots"]:
        shot_id = shot["id"]
        audio_path = audio_paths.get(shot_id)
        narration_duration = ffprobe_duration_s(audio_path) if audio_path is not None else None
        planned = float(shot["duration_s"])
        effective = max(planned, (narration_duration + PAD_S) if narration_duration is not None else planned)
        entries.append(
            {
                "id": shot_id,
                "planned_duration_s": planned,
                "narration_duration_s": round(narration_duration, 3) if narration_duration is not None else None,
                "effective_duration_s": round(effective, 3),
            }
        )
        total += effective

    return {
        "shots": entries,
        "total_effective_duration_s": round(total, 3),
        "in_60_90_range": 60 <= total <= 90,
    }


def run(
    storyboard_path: Path = config.STORYBOARD_PATH, *, shot_filter: str | None = None, force: bool = False
) -> dict[str, Any]:
    storyboard = load_storyboard(storyboard_path)
    shots = storyboard["shots"]
    if shot_filter:
        shots = [s for s in shots if s["id"] == shot_filter]
        if not shots:
            raise ValueError(f"no shot with id {shot_filter!r}")

    for shot in shots:
        generate_shot_narration(shot, force=force)

    # timing.json always reflects ALL shots' audio, not only the ones --shot touched,
    # so regenerating a single shot still yields a complete, usable timing file.
    all_audio_paths = {
        shot["id"]: path for shot in storyboard["shots"] if (path := shot_audio_path(shot)).exists()
    }

    timing = build_timing(storyboard, all_audio_paths)
    config.TIMING_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.TIMING_PATH.write_text(json.dumps(timing, indent=2, ensure_ascii=False) + "\n")

    if not timing["in_60_90_range"]:
        print(
            f"WARNING: total narration-driven duration is {timing['total_effective_duration_s']}s, "
            "outside the 60-90s target. Consider adding/trimming narration lines."
        )
    return timing
