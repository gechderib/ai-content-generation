"""Thin wrappers around the ffmpeg/ffprobe command-line tools.

These are deterministic local operations (not model calls), so they aren't
logged to runs.jsonl the way API/GPU calls are.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class FfmpegError(Exception):
    pass


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise FfmpegError("ffmpeg/ffprobe not found on PATH. Install ffmpeg first (e.g. `sudo apt install ffmpeg`).")


def ffprobe_duration_s(path: Path) -> float:
    require_ffmpeg()
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FfmpegError(f"ffprobe failed on {path}: {result.stderr.strip()}")
    return float(result.stdout.strip())


def run_ffmpeg(args: list[str]) -> None:
    require_ffmpeg()
    result = subprocess.run(["ffmpeg", "-y", *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise FfmpegError(f"ffmpeg failed: {' '.join(args)}\n{result.stderr[-2000:]}")
