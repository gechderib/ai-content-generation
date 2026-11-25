"""shots stage: one moving clip per shot.

Two paths:
- --fallback: a Ken Burns pan/zoom over the shot's keyframe (ffmpeg zoompan),
  no GPU required. This is what lets `make film` produce a complete,
  watchable film even without a Kaggle GPU session.
- --import-dir: ingest a real Wan 2.2 image-to-video clip rendered on Kaggle
  (see notebooks/wan_shots.ipynb), copied in under this stage's cache-key
  filename and logged with its GPU minutes (read from that directory's
  gpu_log.json, which the notebook writes).

Clips are rendered at the keyframe's own square resolution; assemble.py
crops to each export's aspect ratio (9:16, 16:9) from this same centred
material, rather than this stage picking one aspect ratio itself.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config
from .cache import cache_path, hash_file, is_cached, stage_key
from .ffmpeg_utils import run_ffmpeg
from .keyframes import keyframe_path
from .runs_log import log_call
from .schema_validate import load_storyboard

STAGE = "shots"
FPS = 24
FRAME_SIZE = "1024x1024"


def _zoompan_filter(motion_prompt: str, frames: int) -> str:
    """A simple, honest reading of the motion prompt: zoom in, zoom out, or
    hold static. Anything more specific (true panning/tracking) is what the
    real Wan 2.2 import path is for - this is the no-GPU fallback, not a
    replacement for it.
    """
    text = motion_prompt.lower()
    if "static" in text or "fixed" in text or "locked" in text:
        zoom_expr = "1"
    elif "pull" in text or "zoom out" in text:
        zoom_expr = "if(eq(on,0),1.15,max(zoom-0.0012,1.0))"
    else:  # default: gentle push-in (push-in, track, pan all read as this in the fallback)
        zoom_expr = "min(zoom+0.0012,1.18)"
    return f"zoompan=z='{zoom_expr}':d={frames}:s={FRAME_SIZE}:fps={FPS}"


def shot_duration_s(shot_id: str, timing: dict[str, Any]) -> float:
    for t in timing["shots"]:
        if t["id"] == shot_id:
            return t["effective_duration_s"]
    raise KeyError(f"no timing entry for shot {shot_id!r} - run `python -m pipeline narration` first")


def shot_clip_path(shot_id: str, key: str) -> Path:
    return cache_path(STAGE, shot_id, key, "mp4")


def fallback_inputs(shot: dict[str, Any], keyframe: Path, duration_s: float) -> dict[str, Any]:
    return {
        "mode": "fallback_kenburns",
        "keyframe_hash": hash_file(keyframe),
        "motion_prompt": shot["motion_prompt"],
        "duration_s": duration_s,
        "fps": FPS,
    }


def generate_fallback_clip(
    shot: dict[str, Any], storyboard: dict[str, Any], timing: dict[str, Any], *, force: bool = False
) -> Path:
    shot_id = shot["id"]
    kf_path = keyframe_path(shot, storyboard)
    if not kf_path.exists():
        raise FileNotFoundError(f"{shot_id}: no keyframe at {kf_path} - run `python -m pipeline keyframes` first")

    duration_s = shot_duration_s(shot_id, timing)
    key = stage_key(STAGE, fallback_inputs(shot, kf_path, duration_s))
    path = shot_clip_path(shot_id, key)

    if is_cached(path) and not force:
        print(f"[cached]      {shot_id} shot (fallback, {path.name})")
        return path

    frames = max(int(round(duration_s * FPS)), 1)
    zoom = _zoompan_filter(shot["motion_prompt"], frames)
    path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            "-loop", "1", "-i", str(kf_path),
            "-vf", f"scale={FRAME_SIZE},{zoom}",
            "-t", str(duration_s),
            "-r", str(FPS),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(path),
        ]
    )
    log_call(
        stage=STAGE, shot_id=shot_id, model="ffmpeg-kenburns-fallback", status="ok",
        params={"motion_prompt": shot["motion_prompt"], "duration_s": duration_s},
        cache_key=key, output_path=str(path), cost_usd=0.0,
    )
    print(f"[regenerated] {shot_id} shot (fallback, {path.name})")
    return path


def import_shot_clip(shot: dict[str, Any], import_dir: Path, gpu_log: dict[str, Any], *, force: bool = False) -> Path:
    shot_id = shot["id"]
    src = import_dir / f"{shot_id}.mp4"
    if not src.exists():
        raise FileNotFoundError(f"{shot_id}: no imported clip at {src}")

    src_hash = hash_file(src)
    key = stage_key(STAGE, {"mode": "wan_import", "source_hash": src_hash, "motion_prompt": shot["motion_prompt"]})
    path = shot_clip_path(shot_id, key)

    if is_cached(path) and not force:
        print(f"[cached]      {shot_id} shot (imported, {path.name})")
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(src.read_bytes())

    gpu_minutes = (gpu_log.get(shot_id) or {}).get("gpu_minutes")
    log_call(
        stage=STAGE, shot_id=shot_id, model="Wan2.2-TI2V-5B", status="ok",
        params={"motion_prompt": shot["motion_prompt"], "source": str(src)},
        cache_key=key, output_path=str(path), gpu_minutes=gpu_minutes, cost_usd=0.0,
    )
    print(f"[imported]    {shot_id} shot ({path.name})")
    return path


def run(
    storyboard_path: Path = config.STORYBOARD_PATH,
    *,
    shot_filter: str | None = None,
    force: bool = False,
    fallback: bool = False,
    import_dir: str | None = None,
) -> list[Path]:
    storyboard = load_storyboard(storyboard_path)
    shots = storyboard["shots"]
    if shot_filter:
        shots = [s for s in shots if s["id"] == shot_filter]
        if not shots:
            raise ValueError(f"no shot with id {shot_filter!r}")

    if import_dir:
        import_path = Path(import_dir)
        gpu_log_path = import_path / "gpu_log.json"
        gpu_log = json.loads(gpu_log_path.read_text()) if gpu_log_path.exists() else {}
        return [import_shot_clip(shot, import_path, gpu_log, force=force) for shot in shots]

    if fallback:
        if not config.TIMING_PATH.exists():
            raise FileNotFoundError(f"{config.TIMING_PATH} not found - run `python -m pipeline narration` first")
        timing = json.loads(config.TIMING_PATH.read_text())
        return [generate_fallback_clip(shot, storyboard, timing, force=force) for shot in shots]

    raise ValueError("shots stage requires --fallback (no GPU) or --import-dir <dir> (Kaggle output)")
