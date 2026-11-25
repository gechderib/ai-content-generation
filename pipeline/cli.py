"""CLI entry point: `python -m pipeline <stage> [options]`.

Only `validate` is wired up so far; the remaining stages are added one at a time
as their pipeline modules are built (see the project plan in the repo's history).
"""
from __future__ import annotations

import argparse
import sys

from . import config
from .schema_validate import validate_file

STAGES = [
    "validate",
    "smoke",
    "reference",
    "keyframes",
    "narration",
    "radio",
    "music",
    "shots",
    "assemble",
    "all",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline", description="The Starting Price - film pipeline")
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("--shot", help="only process this shot id, e.g. s03")
    parser.add_argument("--force", action="store_true", help="ignore the cache and regenerate")
    parser.add_argument("--draft", action="store_true", help="low-resolution / fast draft mode")
    parser.add_argument("--import-dir", help="import notebook outputs from this directory (shots/music)")
    parser.add_argument("--fallback", action="store_true", help="use the no-GPU fallback (Ken Burns / placeholder bed)")
    return parser


def run_validate(args: argparse.Namespace) -> int:
    errors = validate_file(config.STORYBOARD_PATH)
    if errors:
        print(f"storyboard.json is INVALID ({len(errors)} error(s)):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("storyboard.json is valid.")
    return 0


STAGE_HANDLERS = {
    "validate": run_validate,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = STAGE_HANDLERS.get(args.stage)
    if handler is None:
        print(f"Stage '{args.stage}' is not implemented yet (coming in a later step).", file=sys.stderr)
        return 2
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
