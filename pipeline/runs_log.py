"""Append-only log: one JSON line per model call, written to runs.jsonl.

Every stage calls log_call() for every attempt (including failed ones and
notebook-imported GPU outputs), so runs.jsonl is a complete record of what was
called, with what parameters, at what cost - the evidence the codebase grading
reads instead of opening media files.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config

_SECRET_KEY_NAMES = {"api_key", "token", "x-goog-api-key", "authorization", "cf_api_token", "hf_token"}


def _scrub(params: dict[str, Any]) -> dict[str, Any]:
    return {k: ("<redacted>" if k.lower() in _SECRET_KEY_NAMES else v) for k, v in params.items()}


def log_call(
    *,
    stage: str,
    shot_id: str | None,
    model: str,
    params: dict[str, Any] | None = None,
    seed: int | None = None,
    attempt: int = 1,
    status: str,
    latency_ms: float | None = None,
    gpu_minutes: float | None = None,
    cost_usd: float = 0.0,
    list_price_equivalent_usd: float | None = None,
    cache_key: str | None = None,
    output_path: str | None = None,
    error: str | None = None,
    path: Path | None = None,
) -> None:
    if path is None:
        path = config.RUNS_LOG_PATH
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "shot_id": shot_id,
        "model": model,
        "params": _scrub(params or {}),
        "seed": seed,
        "attempt": attempt,
        "status": status,
        "latency_ms": latency_ms,
        "gpu_minutes": gpu_minutes,
        "cost_usd": cost_usd,
        "list_price_equivalent_usd": list_price_equivalent_usd,
        "cache_key": cache_key,
        "output_path": output_path,
        "error": error,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


class Timer:
    """Context manager measuring wall-clock latency in milliseconds."""

    def __enter__(self) -> "Timer":
        self._start = time.monotonic()
        self.latency_ms: float = 0.0
        return self

    def __exit__(self, *exc: Any) -> None:
        self.latency_ms = (time.monotonic() - self._start) * 1000
