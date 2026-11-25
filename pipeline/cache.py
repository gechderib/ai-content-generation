"""Content-addressed caching.

stage_key(stage, inputs) hashes the canonical JSON of everything that determines
a stage's output for one shot (prompt, style block, character description, seed,
model id, reference-image hash, upstream file hashes). A re-run with the same
inputs produces the same key, so an existing output file is skipped; changing one
shot's prompt or seed changes only that shot's key, leaving its siblings cached.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import OUTPUTS_DIR


def canonical_json(inputs: dict[str, Any]) -> str:
    return json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stage_key(stage: str, inputs: dict[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(inputs).encode("utf-8")).hexdigest()
    return digest[:16]


def hash_file(path: Path) -> str:
    """Hash a file's bytes, for including an upstream output (e.g. a reference image) in inputs."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def cache_path(stage: str, shot_id: str, key: str, ext: str) -> Path:
    return OUTPUTS_DIR / stage / f"{shot_id}_{key}.{ext}"


def is_cached(path: Path) -> bool:
    return path.exists()
