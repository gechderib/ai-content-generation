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
    parser.add_argument("--pick", type=int, help="reference stage: choose a candidate by its variant number as the golden reference")
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


def run_smoke(args: argparse.Namespace) -> int:
    from .smoke import run_all

    ok = True
    for r in run_all():
        model = r.model or "-"
        latency = f"{r.latency_ms:.0f}ms" if r.latency_ms is not None else "-"
        print(f"[{r.status.upper():7}] {r.provider:16} model={model:28} latency={latency}")
        if r.detail:
            print(f"          {r.detail}")
        if r.status == "error":
            ok = False
    return 0 if ok else 1


def run_narration(args: argparse.Namespace) -> int:
    from .narration import run as run_narration_stage

    try:
        run_narration_stage(shot_filter=args.shot, force=args.force)
    except Exception as exc:
        print(f"narration stage failed: {exc}", file=sys.stderr)
        return 1
    return 0


def run_radio(args: argparse.Namespace) -> int:
    from .radio import build_radio_cut

    try:
        path = build_radio_cut()
    except Exception as exc:
        print(f"radio stage failed: {exc}", file=sys.stderr)
        return 1
    print(f"radio cut written to {path}")
    return 0


def run_reference(args: argparse.Namespace) -> int:
    from .reference import generate_candidates, pick

    if args.pick is not None:
        try:
            dest = pick(args.pick)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(f"golden reference set to {dest} (from variant {args.pick})")
        return 0

    try:
        paths = generate_candidates(force=args.force)
    except Exception as exc:
        print(f"reference stage failed: {exc}", file=sys.stderr)
        return 1
    print("Candidates generated. Look at them, then run:")
    print("  python -m pipeline reference --pick <variant>")
    for p in paths:
        print(f"  {p}")
    return 0


def run_keyframes(args: argparse.Namespace) -> int:
    from .keyframes import run as run_keyframes_stage

    try:
        run_keyframes_stage(shot_filter=args.shot, force=args.force)
    except Exception as exc:
        print(f"keyframes stage failed: {exc}", file=sys.stderr)
        return 1
    return 0


def run_shots(args: argparse.Namespace) -> int:
    from .shots import run as run_shots_stage

    try:
        run_shots_stage(
            shot_filter=args.shot, force=args.force, fallback=args.fallback, import_dir=args.import_dir
        )
    except Exception as exc:
        print(f"shots stage failed: {exc}", file=sys.stderr)
        return 1
    return 0


def run_music(args: argparse.Namespace) -> int:
    from .music import run as run_music_stage

    try:
        run_music_stage(force=args.force, fallback=args.fallback, import_dir=args.import_dir)
    except Exception as exc:
        print(f"music stage failed: {exc}", file=sys.stderr)
        return 1
    return 0


def run_assemble(args: argparse.Namespace) -> int:
    from .assemble import run as run_assemble_stage

    try:
        outputs = run_assemble_stage(force=args.force)
    except Exception as exc:
        print(f"assemble stage failed: {exc}", file=sys.stderr)
        return 1
    for aspect, path in outputs.items():
        print(f"  {aspect}: {path}")
    return 0


STAGE_HANDLERS = {
    "validate": run_validate,
    "smoke": run_smoke,
    "narration": run_narration,
    "radio": run_radio,
    "reference": run_reference,
    "keyframes": run_keyframes,
    "shots": run_shots,
    "music": run_music,
    "assemble": run_assemble,
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
