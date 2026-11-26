"""Magic Hour hosted image-to-video: an alternative to the Kaggle/Colab Wan
2.2 GPU path when free-tier 16GB VRAM can't fit ti2v-5B's real >=24GB need
(confirmed live on both platforms - see FAILURES.md). Calls Magic Hour's own
hosted "wan-2.2" model over HTTP - no GPU session, no dependency wrangling -
and writes output in the same {shot_id}.mp4 + gpu_log.json shape
`shots.py --import-dir` already expects, so it plugs into the existing
ingestion path (shots.import_shot_clip reads the model/cost_usd fields this
writes, falling back to its old Wan2.2-on-GPU defaults if absent).

Costs real money per shot (credits, billed in USD - see config.py) - this
module only ever runs when explicitly invoked (`python -m pipeline magichour`),
never as part of `make film` or any --fallback path.

The .env key is MAGICHOUR_API_KEY (no underscore) - note the magic_hour SDK's
own Client() defaults to reading MAGIC_HOUR_API_KEY (with an underscore) if
no token is passed; token is always passed explicitly here so that mismatch
never matters.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config
from .assemble import SHOT_PAD_S
from .keyframes import keyframe_path
from .schema_validate import load_storyboard

STAGE = "magichour"


def _client():
    from magic_hour import Client

    return Client(token=config.get_env("MAGICHOUR_API_KEY"))


def clamp_duration(duration_s: float) -> float:
    return float(max(config.MAGICHOUR_MIN_SECONDS, min(config.MAGICHOUR_MAX_SECONDS, round(duration_s))))


def shot_target_duration_s(shot: dict[str, Any], timing_by_id: dict[str, Any]) -> float:
    """Same pacing basis as assemble.py (narration length + a small pad, not
    the storyboard's pre-narration planned duration_s) - see FAILURES.md for
    why that distinction matters.
    """
    entry = timing_by_id.get(shot["id"], {})
    narration_duration = entry.get("narration_duration_s")
    if narration_duration is not None:
        raw = narration_duration + SHOT_PAD_S
    else:
        raw = entry.get("effective_duration_s", float(shot["duration_s"]))
    return clamp_duration(raw)


def generate_shot_clip(client, shot: dict[str, Any], kf_path: Path, duration_s: float, output_dir: Path) -> dict[str, Any]:
    shot_id = shot["id"]
    response = client.v1.image_to_video.generate(
        assets={"image_file_path": str(kf_path)},
        end_seconds=duration_s,
        model=config.MAGICHOUR_MODEL,
        resolution=config.MAGICHOUR_RESOLUTION,
        style={"prompt": shot["motion_prompt"]},
        name=f"the-starting-price-{shot_id}",
        wait_for_completion=True,
        download_outputs=True,
        download_directory=str(output_dir),
    )
    if response.status != "complete":
        raise RuntimeError(f"{shot_id}: Magic Hour project {response.id} ended with status {response.status!r}: {response.error}")
    if not response.downloaded_paths:
        raise RuntimeError(f"{shot_id}: Magic Hour reported complete but returned no downloaded files")

    downloaded = Path(response.downloaded_paths[0])
    dest = output_dir / f"{shot_id}.mp4"
    downloaded.replace(dest)

    credits_charged = response.credits_charged
    return {
        "path": dest,
        "credits_charged": credits_charged,
        "cost_usd": round(credits_charged * config.MAGICHOUR_USD_PER_CREDIT, 4),
        "duration_s": duration_s,
    }


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

    client = _client()
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
        print(f"Generating {shot_id} ({duration_s:.0f}s, {config.MAGICHOUR_MODEL}, {config.MAGICHOUR_RESOLUTION}): {shot['motion_prompt']!r}")
        result = generate_shot_clip(client, shot, kf, duration_s, output_dir)
        total_cost += result["cost_usd"]

        gpu_log[shot_id] = {
            "model": f"magichour/{config.MAGICHOUR_MODEL}",
            "cost_usd": result["cost_usd"],
            "credits_charged": result["credits_charged"],
            "duration_s": duration_s,
        }
        gpu_log_path.write_text(json.dumps(gpu_log, indent=2))
        print(f"[OK] {shot_id} -> {result['path'].name} ({result['credits_charged']} credits, ${result['cost_usd']:.4f})")

    print(f"Total this run: ${total_cost:.2f}")
    print(f"Next: python -m pipeline shots --import-dir {output_dir}")
    return output_dir
