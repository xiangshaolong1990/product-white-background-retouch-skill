#!/usr/bin/env python3
"""Create one final white-background image without retaining intermediate files."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


SCRIPT_DIR = Path(__file__).resolve().parent
WHITE_RETOUCH = SCRIPT_DIR / "first_mode_retouch.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--approved", type=Path)
    parser.add_argument("--shadow", choices=("none", "subtle"), default="none")
    parser.add_argument("--allow-edge-touch", action="store_true")
    parser.add_argument("--force-process", action="store_true")
    parser.add_argument("--alpha-max-matte-side", type=int, default=3000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = args.input.expanduser()
    if not source.is_file():
        raise SystemExit(f"Input file not found: {source}")
    output = (args.output or source.with_name(f"{source.stem}修.png")).expanduser()
    with tempfile.TemporaryDirectory(prefix="final-white-retouch-") as temporary_directory:
        intermediate = Path(temporary_directory) / "white.png"
        command = [
            sys.executable,
            str(WHITE_RETOUCH),
            "--input",
            str(source),
            "--output",
            str(intermediate),
            "--shadow",
            args.shadow,
            "--edge-mode",
            "alpha",
            "--alpha-max-matte-side",
            str(args.alpha_max_matte_side),
        ]
        if args.allow_edge_touch:
            command.append("--allow-edge-touch")
        if args.force_process:
            command.append("--force-process")
        if args.approved:
            command.extend(("--approved", str(args.approved.expanduser())))
        subprocess.run(command, check=True, capture_output=True, text=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(intermediate, output)
    print(f"Saved final image: {output}")


if __name__ == "__main__":
    main()
