"""assemble stage: combine shot clips, narration, music, subtitles, and the
end card into the finished film, exported at both 9:16 and 16:9.

Picks, per shot, the most-recently-modified outputs/shots/{shot_id}_*.mp4 (so
this transparently picks up whichever source is newest - the no-GPU Ken Burns
fallback, or a real Wan 2.2 clip copied in by `shots --import-dir`). Likewise
outputs/music/score_*.wav (the placeholder pad, or an imported ACE-Step
candidate - both are written under that same filename pattern). Narration is
looked up deterministically via narration.shot_audio_path(shot), since that
stage has no fallback/import notion of its own.

Pipeline, all pure ffmpeg (no model calls, so nothing here writes to
runs.jsonl - see ffmpeg_utils.py):
  1. Build a silent-but-for-narration square (1024x1024) "main track": each
     shot's clip cropped to square and its narration padded to the shot's
     timing.json duration, concatenated in order.
  2. Build the full mixed score: loop/trim the picked music bed to the film's
     total length (main track + end card), duck it under the narration via
     sidechaincompress, mix, and loudnorm to ~-14 LUFS.
  3. For each aspect ratio: crop the main track's video to that aspect, burn
     in English subtitles + overlay_text price captions (sized for that
     aspect's own canvas - burned after cropping, not before, so cropping
     never slices through subtitle text), append an end card clip, and mux
     with the shared final audio.

Clips/keyframes are composed square with a centred subject (style_block:
"vertical-friendly centred composition"), which is what makes a single shared
master safe to crop two ways instead of rendering each aspect from scratch.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from . import config
from .cache import hash_file, stage_key
from .ffmpeg_utils import ffprobe_duration_s, run_ffmpeg
from .narration import shot_audio_path
from .schema_validate import load_storyboard

STAGE = "assemble"
FRAME_SIZE = 1024
FPS = 24
ASPECTS = {
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Magic Hour's free-tier watermark ("Magic Hour" wordmark, bottom-right of
# every clip it generates) is wide enough (measured live: ~40% of frame
# width) that cropping it out would mean either losing a large slice of each
# shot's right side or stretching the whole frame to compensate - both worse
# than just hiding it. Blurred out in place instead, at FRAME_SIZE scale.
# Measured directly on a real Magic Hour clip (1024x1024): the wordmark
# itself only spans y=939-999 (60px tall); this box adds a small margin
# around that rather than the much taller first guess, which was blurring
# real picture (the mother's dress hem/shoes) well above the actual logo.
# Harmless on non-Magic Hour sources (fallback Ken Burns clips, real Wan 2.2
# imports) - just blurs an empty background corner there.
WATERMARK_CROP = (560, 915, 464, 109)  # x, y, width, height

# timing.json's effective_duration_s pads each shot to at least its planned
# duration_s, a screen-time estimate from storyboard.json written before any
# narration existed. The narration usually finishes well before that (e.g.
# 5.25s read vs. a 7.0s plan), so holding the shot open for the full planned
# length leaves a silent-but-for-music gap between lines. Confirmed too long
# by ear on the first assembled cut - paced on the narration's own length
# instead (same idea as radio.py's GAP_S, a fixed small breathing pause
# rather than the planning estimate).
SHOT_PAD_S = 0.4

DUCK_THRESHOLD = 0.05
DUCK_RATIO = 8
LOUDNORM_I = -14.0
LOUDNORM_TP = -1.5
LOUDNORM_LRA = 11.0

FINAL_DIR = config.OUTPUTS_DIR / "final"


def _latest(pattern: str) -> Path:
    matches = sorted(config.OUTPUTS_DIR.glob(pattern), key=lambda p: p.stat().st_mtime)
    if not matches:
        raise FileNotFoundError(f"no file matching outputs/{pattern} - run the earlier stages first")
    return matches[-1]


def pick_shot_clip(shot_id: str) -> Path:
    return _latest(f"shots/{shot_id}_*.mp4")


def pick_music_bed() -> Path:
    return _latest("music/score_*.wav")


def shots_timeline(storyboard: dict[str, Any], timing: dict[str, Any]) -> list[dict[str, Any]]:
    timing_by_id = {t["id"]: t for t in timing["shots"]}
    entries = []
    start = 0.0
    for shot in storyboard["shots"]:
        t = timing_by_id[shot["id"]]
        narration_duration = t.get("narration_duration_s")
        duration = round(narration_duration + SHOT_PAD_S, 3) if narration_duration is not None else t["effective_duration_s"]
        entries.append(
            {
                "id": shot["id"],
                "start": round(start, 3),
                "duration": duration,
                "subtitle_en": shot.get("subtitle_en"),
                "overlay_text": shot.get("overlay_text"),
            }
        )
        start += duration
    return entries


def _assemble_inputs(storyboard: dict[str, Any], timeline: list[dict[str, Any]], music_bed: Path) -> dict[str, Any]:
    shot_hashes = {}
    for shot in storyboard["shots"]:
        shot_hashes[shot["id"]] = {
            "clip": hash_file(pick_shot_clip(shot["id"])),
            "narration": hash_file(shot_audio_path(shot)),
        }
    return {
        "mode": "assemble",
        "shots": shot_hashes,
        "music_hash": hash_file(music_bed),
        "timeline": timeline,
        "end_card": storyboard["end_card"],
    }


def _ass_time(seconds: float) -> str:
    cs = max(round(seconds * 100), 0)
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{c:02d}"


def _ass_escape(text: str) -> str:
    return text.replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def build_ass(timeline: list[dict[str, Any]], width: int, height: int, path: Path) -> Path:
    subtitle_fontsize = max(round(height * 0.033), 24)
    price_fontsize = max(round(height * 0.045), 28)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,{subtitle_fontsize},&H00FFFFFF,&H00000000,&H80000000,0,0,1,2,1,2,60,60,{round(height * 0.06)},1
Style: Price,DejaVu Sans,{price_fontsize},&H0038D1F0,&H00000000,&H80000000,1,0,1,3,1,8,60,60,{round(height * 0.06)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for entry in timeline:
        start, end = entry["start"], entry["start"] + entry["duration"]
        if entry["subtitle_en"]:
            text = _ass_escape(entry["subtitle_en"])
            lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}\n")
        if entry["overlay_text"]:
            o_end = start + min(2.5, entry["duration"])
            text = _ass_escape(entry["overlay_text"])
            lines.append(f"Dialogue: 1,{_ass_time(start)},{_ass_time(o_end)},Price,,0,0,0,,{text}\n")
    path.write_text("".join(lines), encoding="utf-8")
    return path


def build_main_track(storyboard: dict[str, Any], timeline: list[dict[str, Any]], work_dir: Path) -> Path:
    """Silent-but-for-narration square video: each shot's clip cropped to
    1024x1024 and its narration padded to the shot's own timing-driven
    duration, concatenated in shot order.
    """
    path = work_dir / "main_track.mp4"
    segments = []
    for shot, entry in zip(storyboard["shots"], timeline):
        clip = pick_shot_clip(shot["id"])
        narration = shot_audio_path(shot)
        seg_path = work_dir / f"seg_{shot['id']}.mp4"
        wm_x, wm_y, wm_w, wm_h = WATERMARK_CROP
        run_ffmpeg(
            [
                "-stream_loop", "-1", "-i", str(clip),
                "-i", str(narration),
                "-filter_complex",
                f"[0:v]scale={FRAME_SIZE}:{FRAME_SIZE}:force_original_aspect_ratio=increase,"
                f"crop={FRAME_SIZE}:{FRAME_SIZE},setsar=1,fps={FPS}[base];"
                f"[base]split=2[base1][base2];"
                f"[base1]crop={wm_w}:{wm_h}:{wm_x}:{wm_y},boxblur=20:2[wmblur];"
                f"[base2][wmblur]overlay={wm_x}:{wm_y}[v];"
                f"[1:a]aformat=sample_rates=44100:channel_layouts=mono,apad=whole_dur={entry['duration']}[a]",
                "-map", "[v]", "-map", "[a]",
                "-t", str(entry["duration"]),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                str(seg_path),
            ]
        )
        segments.append(seg_path)

    listfile = work_dir / "main_list.txt"
    listfile.write_text("".join(f"file '{s.resolve()}'\n" for s in segments))
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(path)])
    return path


def build_final_audio(
    main_track: Path, music_bed: Path, end_card_duration_s: float, work_dir: Path
) -> tuple[Path, float]:
    main_duration_s = ffprobe_duration_s(main_track)
    total_duration_s = round(main_duration_s + end_card_duration_s, 3)

    narration_padded = work_dir / "narration_padded.wav"
    run_ffmpeg(
        [
            "-i", str(main_track),
            "-filter_complex", f"[0:a]apad=whole_dur={total_duration_s}[a]",
            "-map", "[a]", "-t", str(total_duration_s),
            str(narration_padded),
        ]
    )

    music_full = work_dir / "music_full.wav"
    run_ffmpeg(
        [
            "-stream_loop", "-1", "-i", str(music_bed),
            "-filter_complex", "[0:a]aformat=sample_rates=44100:channel_layouts=mono[a]",
            "-map", "[a]", "-t", str(total_duration_s),
            str(music_full),
        ]
    )

    ducked = work_dir / "music_ducked.wav"
    run_ffmpeg(
        [
            "-i", str(music_full), "-i", str(narration_padded),
            "-filter_complex",
            f"[0:a][1:a]sidechaincompress=threshold={DUCK_THRESHOLD}:ratio={DUCK_RATIO}:"
            f"attack=20:release=300:makeup=1[duck]",
            "-map", "[duck]", str(ducked),
        ]
    )

    premix = work_dir / "premix.wav"
    run_ffmpeg(
        [
            "-i", str(ducked), "-i", str(narration_padded),
            "-filter_complex",
            "[0:a]volume=0.9[m];[1:a]volume=1.0[n];[m][n]amix=inputs=2:duration=longest:normalize=0[mix]",
            "-map", "[mix]", str(premix),
        ]
    )

    final_audio = work_dir / "final_audio.wav"
    run_ffmpeg(
        [
            "-i", str(premix),
            "-af", f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}",
            "-ar", "44100",
            str(final_audio),
        ]
    )
    return final_audio, total_duration_s


def build_end_card(storyboard: dict[str, Any], width: int, height: int, work_dir: Path) -> Path:
    end_card = storyboard["end_card"]
    path = work_dir / f"endcard_{width}x{height}.mp4"
    fontsize = max(round(height * 0.055), 32)
    text = end_card["text"].replace("'", r"\'").replace(":", r"\:")
    run_ffmpeg(
        [
            "-f", "lavfi", "-i", f"color=c=0x1a1a1a:s={width}x{height}:r={FPS}:d={end_card['duration_s']}",
            "-vf",
            f"drawtext=fontfile={FONT}:text='{text}':fontcolor=white:fontsize={fontsize}:"
            f"x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(path),
        ]
    )
    return path


def build_export(
    storyboard: dict[str, Any],
    timeline: list[dict[str, Any]],
    main_track: Path,
    final_audio: Path,
    aspect: str,
    work_dir: Path,
) -> Path:
    width, height = ASPECTS[aspect]
    ass_path = build_ass(timeline, width, height, work_dir / f"subs_{aspect}.ass")

    # Scale the square master so its larger side matches the target's larger
    # side, then centre-crop the smaller side down - a width-crop for 9:16
    # (keeps full height), a height-crop for 16:9 (keeps full width).
    scale_dim = max(width, height)
    cropped = work_dir / f"cropped_{aspect}.mp4"
    run_ffmpeg(
        [
            "-i", str(main_track), "-an",
            "-vf", f"scale={scale_dim}:{scale_dim},crop={width}:{height},ass={ass_path}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            str(cropped),
        ]
    )

    end_card = build_end_card(storyboard, width, height, work_dir)

    full_visual = work_dir / f"full_visual_{aspect}.mp4"
    listfile = work_dir / f"visual_list_{aspect}.txt"
    listfile.write_text(f"file '{cropped.resolve()}'\nfile '{end_card.resolve()}'\n")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listfile), "-c", "copy", str(full_visual)])

    final_path = work_dir / f"final_{aspect}.mp4"
    run_ffmpeg(
        [
            "-i", str(full_visual), "-i", str(final_audio),
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(final_path),
        ]
    )
    return final_path


def run(storyboard_path: Path = config.STORYBOARD_PATH, *, force: bool = False) -> dict[str, Path]:
    storyboard = load_storyboard(storyboard_path)
    if not config.TIMING_PATH.exists():
        raise FileNotFoundError(f"{config.TIMING_PATH} not found - run `python -m pipeline narration` first")
    timing = json.loads(config.TIMING_PATH.read_text())
    timeline = shots_timeline(storyboard, timing)
    music_bed = pick_music_bed()

    key = stage_key(STAGE, _assemble_inputs(storyboard, timeline, music_bed))
    work_dir = config.OUTPUTS_DIR / STAGE / key
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    outputs = {aspect: FINAL_DIR / f"{aspect}.mp4" for aspect in ASPECTS}
    marker = work_dir / "DONE"
    if marker.exists() and not force:
        print(f"[cached]      assemble ({key})")
        for aspect, dest in outputs.items():
            cached = work_dir / f"final_{aspect}.mp4"
            if not dest.exists() or dest.stat().st_mtime < cached.stat().st_mtime:
                shutil.copy(cached, dest)
        return outputs

    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    print(f"[assembling]  main track ({len(timeline)} shots)")
    main_track = build_main_track(storyboard, timeline, work_dir)

    print("[assembling]  score (duck + mix + loudnorm)")
    final_audio, total_duration_s = build_final_audio(
        main_track, music_bed, storyboard["end_card"]["duration_s"], work_dir
    )
    print(f"  total film length: {total_duration_s:.1f}s")

    for aspect in ASPECTS:
        print(f"[assembling]  {aspect} export")
        final_path = build_export(storyboard, timeline, main_track, final_audio, aspect, work_dir)
        shutil.copy(final_path, outputs[aspect])
        print(f"[regenerated] {aspect} -> {outputs[aspect]}")

    marker.write_text(key)
    return outputs
