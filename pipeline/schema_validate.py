"""Validate storyboard.json against schema/storyboard.schema.json, plus the
cross-field rules a JSON Schema can't express on its own (unique shot ids, and
total shot duration between 60 and 90 seconds).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from .config import SCHEMA_PATH, STORYBOARD_PATH


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def load_storyboard(path: Path = STORYBOARD_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def _format_schema_error(err: jsonschema.exceptions.ValidationError) -> str:
    path = "/".join(str(p) for p in err.absolute_path) or "<root>"
    return f"{path}: {err.message}"


def validate_storyboard(storyboard: dict[str, Any], schema: dict[str, Any] | None = None) -> list[str]:
    """Return a list of human-readable error strings; an empty list means valid."""
    schema = schema if schema is not None else load_schema()
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    errors = [_format_schema_error(e) for e in sorted(validator.iter_errors(storyboard), key=str)]

    shots = storyboard.get("shots")
    if isinstance(shots, list) and shots:
        ids = [s.get("id") for s in shots if isinstance(s, dict)]
        seen: set[Any] = set()
        dupes: set[Any] = set()
        for sid in ids:
            if sid in seen:
                dupes.add(sid)
            seen.add(sid)
        if dupes:
            errors.append(f"shots: duplicate shot id(s): {sorted(dupes)}")

        durations = [
            s.get("duration_s") for s in shots if isinstance(s, dict) and isinstance(s.get("duration_s"), (int, float))
        ]
        if len(durations) == len(shots):
            total = sum(durations)
            if not (60 <= total <= 90):
                errors.append(f"shots: total duration_s is {total}s, must be between 60 and 90")

    return errors


def validate_file(path: Path = STORYBOARD_PATH) -> list[str]:
    return validate_storyboard(load_storyboard(path))
