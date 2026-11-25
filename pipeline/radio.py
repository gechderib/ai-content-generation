"""radio stage: narration cut together over a quiet placeholder bed on a black
screen - the cheapest prototype to test the story and its timing before any
pictures exist (Phase 1's radio cut / "audio animatic").

The placeholder bed is a synthesised quiet tone (ffmpeg's `sine` source), not
real music - ACE-Step candidates come later in the music stage. Its only job
here is to give the radio cut something under the voice so the mix isn't
narration on dead silence.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import config
from .ffmpeg_utils import run_ffmpeg
from .narration import shot_audio_path
from .schema_validate import load_storyboard

OUTPUT_PATH = config.OUTPUTS_DIR / "final" / "radio_cut.mp4"

# A natural breathing pause between lines, not the shot's planned screen time.
# timing.json's effective_duration_s (used by the later shots/assemble stages)
# stretches each shot to at least its planned duration_s, because real visuals
# will eventually fill that time. The radio cut has no visuals yet, so padding
# to that same length just inserts a long silence between sentences and makes
# the story drag. Here we pace on the narration's own length instead.
GAP_S = 0.4


def build_ffmpeg_args(audio_paths: list[Path], durations: list[float], total_duration: float, output_path: Path) -> list[str]:
    """Pure: given per-shot narration paths/durations and a total length, build the
    ffmpeg argument list for the radio cut. Kept separate from any filesystem or
    subprocess work so it's directly unit-testable.
    """
    inputs: list[str] = []
    for path in audio_paths:
        inputs += ["-i", str(path)]

    filter_parts = []
    labels = []
    for i, dur in enumerate(durations):
        filter_parts.append(f"[{i}:a]apad=whole_dur={dur}[a{i}]")
        labels.append(f"[a{i}]")
    filter_parts.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[voice]")

    bed_idx = len(audio_paths)
    inputs += ["-f", "lavfi", "-i", f"sine=frequency=220:duration={total_duration}:sample_rate=44100"]
    filter_parts.append(f"[{bed_idx}:a]volume=0.05[bed]")
    filter_parts.append("[voice][bed]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[mix]")

    video_idx = bed_idx + 1
    inputs += ["-f", "lavfi", "-i", f"color=c=black:s=1080x1920:r=24:d={total_duration}"]

    return [
        *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", f"{video_idx}:v",
        "-map", "[mix]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        str(output_path),
    ]


def build_radio_cut(
    storyboard_path: Path = config.STORYBOARD_PATH,
    timing_path: Path = config.TIMING_PATH,
    output_path: Path = OUTPUT_PATH,
) -> Path:
    storyboard = load_storyboard(storyboard_path)
    if not timing_path.exists():
        raise FileNotFoundError(f"{timing_path} not found - run `python -m pipeline narration` first")
    timing = json.loads(timing_path.read_text())
    timing_by_id = {t["id"]: t for t in timing["shots"]}

    audio_paths: list[Path] = []
    durations: list[float] = []
    for shot in storyboard["shots"]:
        path = shot_audio_path(shot)
        if not path.exists():
            raise FileNotFoundError(
                f"{shot['id']}: narration audio not found at {path} - run `python -m pipeline narration` first"
            )
        shot_timing = timing_by_id[shot["id"]]
        narration_duration = shot_timing.get("narration_duration_s") or shot_timing["effective_duration_s"]
        audio_paths.append(path)
        durations.append(round(narration_duration + GAP_S, 3))

    total_duration = sum(durations) + storyboard["end_card"]["duration_s"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    args = build_ffmpeg_args(audio_paths, durations, total_duration, output_path)
    run_ffmpeg(args)
    return output_path
