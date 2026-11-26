"""Agnes AI hosted image-to-video: an alternative to the Kaggle/Colab Wan 2.2
GPU path (and to Magic Hour, tried first - see git history/FAILURES.md; that
account ran out of starter credits after 3 shots). Calls Agnes AI's
"keyframe" mode (POST /v1/videos, model agnes-video-2.5-flash) over plain
HTTP via `requests` (already a dependency, no new SDK needed). Writes output
in the same {shot_id}.mp4 + gpu_log.json shape `shots.py --import-dir`
expects.

Real constraint, confirmed live against docs.agnes-ai.com: Agnes only
accepts a publicly reachable image URL for `first_frame` - no upload/base64
field is documented. Each local keyframe is hosted via Cloudinary's unsigned
upload API (an established service with a free tier, no payment method
required) just long enough for the API call. These are stylized illustration
stills of fictional characters, never the real reference photos (see
ETHICS.md), so public exposure was judged an acceptable trade-off - flagged
to the user before building this. Two earlier options were tried and ruled
out (see config.py/FAILURES.md): Cloudflare R2 requires a payment method on
file even for its free tier; anonymous throwaway hosts (catbox.moe/litterbox,
0x0.st) have both locked down anonymous uploads due to AI-agent abuse.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from . import config
from .assemble import SHOT_PAD_S
from .http import request_with_retry
from .keyframes import keyframe_path
from .schema_validate import load_storyboard

STAGE = "agnes"
POLL_INTERVAL_S = 2.0
POLL_TIMEOUT_S = 600.0


def clamp_duration(duration_s: float) -> int:
    return int(max(config.AGNES_MIN_SECONDS, min(config.AGNES_MAX_SECONDS, round(duration_s))))


def shot_target_duration_s(shot: dict[str, Any], timing_by_id: dict[str, Any]) -> int:
    """Same pacing basis as assemble.py (narration length + a small pad, not
    the storyboard's pre-narration planned duration_s) - see FAILURES.md.
    """
    entry = timing_by_id.get(shot["id"], {})
    narration_duration = entry.get("narration_duration_s")
    if narration_duration is not None:
        raw = narration_duration + SHOT_PAD_S
    else:
        raw = entry.get("effective_duration_s", float(shot["duration_s"]))
    return clamp_duration(raw)


def upload_to_cloudinary(image_path: Path) -> str:
    cloud_name = config.get_env("CLOUDINARY_CLOUD_NAME")
    preset = config.get_env("CLOUDINARY_UPLOAD_PRESET")
    url = config.CLOUDINARY_UPLOAD_URL_TEMPLATE.format(cloud_name=cloud_name)
    with open(image_path, "rb") as f:
        resp = requests.post(
            url,
            data={"upload_preset": preset},
            files={"file": (image_path.name, f, "image/jpeg")},
            timeout=60,
        )
    if resp.status_code >= 400:
        raise RuntimeError(f"Cloudinary upload for {image_path} failed ({resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    secure_url = data.get("secure_url")
    if not secure_url:
        raise RuntimeError(f"Cloudinary upload for {image_path} returned no secure_url: {data}")
    return secure_url


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.get_env('AGNES_API_KEY')}",
        "Content-Type": "application/json",
    }


def create_video_task(image_url: str, prompt: str, duration_s: int) -> dict[str, Any]:
    body = {
        "model": config.AGNES_MODEL,
        "prompt": prompt,
        "mode": "keyframe",
        "first_frame": image_url,
        "seconds": str(duration_s),
        "size": config.AGNES_SIZE,
        # keyframe mode rejects aspect_ratio outright (confirmed live: 400
        # "output follows the input image") - our keyframes are already
        # square, so this is what we want anyway.
    }
    # request_with_retry backs off on 503 (confirmed live: Agnes returns
    # "video_queue_full" under load - its own message says "please retry
    # later", and this was observed persisting for several minutes straight,
    # not a one-off blip, so this needs a patient retry budget: 8 attempts,
    # exponential backoff capped at 60s between tries (~8 minutes total
    # worst case) rather than the default few-second budget) and raises
    # immediately on 400 without retrying.
    result = request_with_retry(
        "POST", f"{config.AGNES_API_BASE}/videos",
        headers=_headers(), json_body=body, max_attempts=8, backoff_cap_s=60.0,
    )
    return result.response.json()


def poll_video_task(video_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_S
    while True:
        result = request_with_retry(
            "GET", config.AGNES_API_STATUS_URL,
            headers=_headers(), params={"video_id": video_id, "model_name": config.AGNES_MODEL},
            max_attempts=2, timeout=30.0,
        )
        data = result.response.json()
        status = data.get("status")
        if status in ("completed", "failed"):
            return data
        if time.monotonic() > deadline:
            raise TimeoutError(f"Agnes AI video {video_id} still {status!r} after {POLL_TIMEOUT_S:.0f}s")
        time.sleep(POLL_INTERVAL_S)


def generate_shot_clip(shot: dict[str, Any], kf_path: Path, duration_s: int, output_dir: Path) -> dict[str, Any]:
    shot_id = shot["id"]
    image_url = upload_to_cloudinary(kf_path)
    task = create_video_task(image_url, shot["motion_prompt"], duration_s)
    video_id = task.get("video_id") or task.get("id")
    if not video_id:
        raise RuntimeError(f"{shot_id}: Agnes AI create response had no video_id/id: {task}")

    result = poll_video_task(video_id)
    if result.get("status") != "completed":
        raise RuntimeError(
            f"{shot_id}: Agnes AI video {video_id} ended with status {result.get('status')!r}: {result.get('error')}"
        )

    video_url = result.get("url")
    if not video_url:
        raise RuntimeError(f"{shot_id}: Agnes AI reported completed but returned no 'url': {result}")

    dest = output_dir / f"{shot_id}.mp4"
    video_resp = requests.get(video_url, timeout=120)
    video_resp.raise_for_status()
    dest.write_bytes(video_resp.content)

    return {"path": dest, "duration_s": duration_s, "cost_usd": round(duration_s * config.AGNES_USD_PER_SECOND, 4)}


def run(
    storyboard_path: Path = config.STORYBOARD_PATH,
    timing_path: Path = config.TIMING_PATH,
    output_dir: Path = config.OUTPUTS_DIR / STAGE,
    *,
    shot_filter: str | None = None,
) -> Path:
    storyboard = load_storyboard(storyboard_path)
    if not timing_path.exists():
        raise FileNotFoundError(f"{timing_path} not found - run `python -m pipeline narration` first")
    timing = json.loads(timing_path.read_text())
    timing_by_id = {t["id"]: t for t in timing["shots"]}

    shots = storyboard["shots"]
    if shot_filter:
        shots = [s for s in shots if s["id"] == shot_filter]
        if not shots:
            raise ValueError(f"no shot with id {shot_filter!r}")

    output_dir.mkdir(parents=True, exist_ok=True)
    gpu_log_path = output_dir / "gpu_log.json"
    gpu_log = json.loads(gpu_log_path.read_text()) if gpu_log_path.exists() else {}

    total_cost = 0.0
    for shot in shots:
        shot_id = shot["id"]
        out_path = output_dir / f"{shot_id}.mp4"
        if out_path.exists():
            print(f"[skip] {shot_id} already generated ({out_path.name})")
            continue

        kf = keyframe_path(shot, storyboard)
        if not kf.exists():
            raise FileNotFoundError(f"{shot_id}: no keyframe at {kf} - run `python -m pipeline keyframes` first")

        duration_s = shot_target_duration_s(shot, timing_by_id)
        print(f"Generating {shot_id} ({duration_s}s, {config.AGNES_MODEL}, {config.AGNES_SIZE}): {shot['motion_prompt']!r}")
        result = generate_shot_clip(shot, kf, duration_s, output_dir)
        total_cost += result["cost_usd"]

        gpu_log[shot_id] = {
            "model": f"agnes/{config.AGNES_MODEL}",
            "cost_usd": result["cost_usd"],
            "duration_s": duration_s,
        }
        gpu_log_path.write_text(json.dumps(gpu_log, indent=2))
        print(f"[OK] {shot_id} -> {result['path'].name} (${result['cost_usd']:.4f})")

    print(f"Total this run: ${total_cost:.2f}")
    print(f"Next: python -m pipeline shots --import-dir {output_dir}")
    return output_dir
