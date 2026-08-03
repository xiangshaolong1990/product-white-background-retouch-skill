#!/usr/bin/env python3
"""Apply the approved first-version white-background workflow quickly."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_SCRIPT = SCRIPT_DIR / "product_white_background_retouch.py"
APPROVED_FOLDER = "白底"
APPROVED_SUFFIX = "-1"
OUTPUT_SUFFIX = "修_第一版模式"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Source product image")
    parser.add_argument("--output", type=Path, help="Output PNG; defaults beside the source")
    parser.add_argument("--approved", type=Path, help="Explicit approved first-version PNG")
    parser.add_argument(
        "--force-process",
        action="store_true",
        help="Ignore approved assets and run the fallback processor",
    )
    parser.add_argument(
        "--fallback-mode",
        choices=("background", "cutout"),
        default="background",
        help="Use background for translucent eyewear; cutout only for opaque products",
    )
    parser.add_argument(
        "--shadow",
        choices=("none", "subtle"),
        default="subtle",
        help="Only applies to cutout fallback mode",
    )
    parser.add_argument("--debug-subject-mask", type=Path)
    parser.add_argument("--debug-background-mask", type=Path)
    return parser.parse_args()


def default_output(source: Path) -> Path:
    return source.with_name(f"{source.stem}{OUTPUT_SUFFIX}.png")


def approved_candidates(source: Path, explicit: Path | None) -> list[Path]:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit.expanduser())
    candidates.extend(
        (
            source.parent / APPROVED_FOLDER / f"{source.stem}{APPROVED_SUFFIX}.png",
            source.parent / APPROVED_FOLDER / f"{source.stem}{APPROVED_SUFFIX}.PNG",
        )
    )
    return candidates


def validate_image(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image.load()
        width, height = image.size
        rgb = image.convert("RGB")
        corners = (
            rgb.getpixel((0, 0)),
            rgb.getpixel((width - 1, 0)),
            rgb.getpixel((0, height - 1)),
            rgb.getpixel((width - 1, height - 1)),
        )
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid output dimensions: {path}")
    if any(pixel != (255, 255, 255) for pixel in corners):
        raise RuntimeError(f"Output corners are not pure white: {path}")
    return width, height


def copy_approved(source: Path, output: Path) -> bool:
    if source.resolve() == output.resolve():
        validate_image(output)
        return True
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output)
    validate_image(output)
    return True


def run_fallback(args: argparse.Namespace, output: Path) -> None:
    if not BASE_SCRIPT.is_file():
        raise RuntimeError(f"Base retouch script not found: {BASE_SCRIPT}")
    command = [
        sys.executable,
        str(BASE_SCRIPT),
        "--input",
        str(args.input),
        "--output",
        str(output),
        "--mode",
        args.fallback_mode,
    ]
    if args.fallback_mode == "cutout":
        command.extend(("--shadow", args.shadow))
    if args.debug_subject_mask:
        command.extend(("--debug-subject-mask", str(args.debug_subject_mask)))
    if args.debug_background_mask:
        command.extend(("--debug-background-mask", str(args.debug_background_mask)))
    subprocess.run(command, check=True)
    validate_image(output)


def main() -> None:
    args = parse_args()
    args.input = args.input.expanduser()
    if not args.input.is_file():
        raise SystemExit(f"Input file not found: {args.input}")
    output = (args.output or default_output(args.input)).expanduser()

    if not args.force_process:
        for candidate in approved_candidates(args.input, args.approved):
            if candidate.is_file():
                copy_approved(candidate, output)
                width, height = validate_image(output)
                print(f"Saved: {output}")
                print(f"Mode: approved-fast-path; source: {candidate}")
                print(f"Output size: {width}x{height}")
                return

    run_fallback(args, output)
    width, height = validate_image(output)
    print(f"Saved: {output}")
    print(f"Mode: {args.fallback_mode}-fallback; visual QA required")
    print(f"Output size: {width}x{height}")


if __name__ == "__main__":
    main()
