"""music stage: the film's score.

Two paths:
- --fallback: a quiet two-note placeholder pad for the full film length, no
  GPU required - just enough texture under the narration so assemble.py has
  something to mix before a real score exists.
- --import-dir: ingest ACE-Step candidates rendered on Kaggle (see
  notebooks/ace_step_music.ipynb), logged with GPU minutes. Listening to the
  candidates and picking a favourite (with a reason, in EXPERIMENTS.md) is a
  human step done after import, not automated here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import config
from .cache import cache_path, hash_file, is_cached, stage_key
from .ffmpeg_utils import run_ffmpeg
from .runs_log import log_call
from .schema_validate import load_storyboard

STAGE = "music"


def total_duration_s(storyboard: dict[str, Any], timing: dict[str, Any]) -> float:
    return timing["total_effective_duration_s"] + storyboard["end_card"]["duration_s"]


def music_path(key: str, ext: str = "wav") -> Path:
    return cache_path(STAGE, "score", key, ext)


def fallback_inputs(storyboard: dict[str, Any], duration_s: float) -> dict[str, Any]:
    m = storyboard["music"]
    return {"mode": "fallback_pad", "bpm": m["bpm"], "instrumental": m["instrumental"], "duration_s": duration_s}


def generate_fallback_bed(
    storyboard_path: Path = config.STORYBOARD_PATH, timing_path: Path = config.TIMING_PATH, *, force: bool = False
) -> Path:
    storyboard = load_storyboard(storyboard_path)
    if not timing_path.exists():
        raise FileNotFoundError(f"{timing_path} not found - run `python -m pipeline narration` first")
    timing = json.loads(timing_path.read_text())
    duration_s = total_duration_s(storyboard, timing)

    key = stage_key(STAGE, fallback_inputs(storyboard, duration_s))
    path = music_path(key)

    if is_cached(path) and not force:
        print(f"[cached]      score (fallback, {path.name})")
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    # A soft root+fifth pad, well below narration level - texture, not a tune.
    root_hz = 220.0
    fifth_hz = root_hz * 1.5
    run_ffmpeg(
        [
            "-f", "lavfi", "-i", f"sine=frequency={root_hz}:duration={duration_s}:sample_rate=44100",
            "-f", "lavfi", "-i", f"sine=frequency={fifth_hz}:duration={duration_s}:sample_rate=44100",
            "-filter_complex",
            "[0:a]volume=0.06[a0];[1:a]volume=0.04[a1];[a0][a1]amix=inputs=2:duration=first:normalize=0[out]",
            "-map", "[out]",
            str(path),
        ]
    )
    log_call(
        stage=STAGE, shot_id=None, model="ffmpeg-placeholder-pad", status="ok",
        params={"bpm": storyboard["music"]["bpm"], "duration_s": duration_s},
        cache_key=key, output_path=str(path), cost_usd=0.0,
    )
    print(f"[regenerated] score (fallback, {path.name})")
    return path


def import_candidates(
    import_dir: str, storyboard_path: Path = config.STORYBOARD_PATH, *, force: bool = False
) -> list[Path]:
    storyboard = load_storyboard(storyboard_path)
    import_path = Path(import_dir)
    gpu_log_path = import_path / "gpu_log.json"
    gpu_log = json.loads(gpu_log_path.read_text()) if gpu_log_path.exists() else {}

    candidates = sorted(import_path.glob("cand*.wav"))
    if not candidates:
        raise FileNotFoundError(f"no cand*.wav files found in {import_path}")

    results = []
    for src in candidates:
        src_hash = hash_file(src)
        key = stage_key(
            STAGE, {"mode": "acestep_import", "source_hash": src_hash, "caption": storyboard["music"]["caption"]}
        )
        path = music_path(key)
        if is_cached(path) and not force:
            print(f"[cached]      {src.name} (imported, {path.name})")
            results.append(path)
            continue

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(src.read_bytes())
        gpu_minutes = (gpu_log.get(src.stem) or {}).get("gpu_minutes")
        log_call(
            stage=STAGE, shot_id=None, model="ACE-Step-1.5", status="ok",
            params={"source": src.name, "caption": storyboard["music"]["caption"]},
            cache_key=key, output_path=str(path), gpu_minutes=gpu_minutes, cost_usd=0.0,
        )
        print(f"[imported]    {src.name} -> {path.name}")
        results.append(path)
    return results


def run(*, force: bool = False, fallback: bool = False, import_dir: str | None = None) -> list[Path]:
    if import_dir:
        return import_candidates(import_dir, force=force)
    if fallback:
        return [generate_fallback_bed(force=force)]
    raise ValueError("music stage requires --fallback (no GPU) or --import-dir <dir> (Kaggle output)")
