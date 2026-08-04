#!/usr/bin/env python3
"""Install the optional PyMatting runtime into the skill cache."""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import subprocess
import sys


DEFAULT_VENV = Path.home() / ".cache" / "codex-product-white-background-retouch" / "alpha-matting-venv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", type=Path, default=DEFAULT_VENV)
    parser.add_argument("--python", type=Path)
    return parser.parse_args()


def default_python() -> Path:
    system_python = Path("/usr/bin/python3")
    if platform.system() == "Darwin" and system_python.is_file():
        return system_python
    return Path(sys.executable)


def main() -> None:
    args = parse_args()
    base_python = (args.python or default_python()).expanduser()
    venv = args.venv.expanduser()
    venv.parent.mkdir(parents=True, exist_ok=True)
    if not (venv / "bin" / "python").is_file():
        subprocess.run([str(base_python), "-m", "venv", str(venv)], check=True)
    python = venv / "bin" / "python"
    subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "pymatting==1.1.15"], check=True)
    subprocess.run(
        [str(python), "-c", "import numpy, scipy, numba, pymatting, PIL"],
        check=True,
    )
    print(f"Alpha matting runtime: {python}")


if __name__ == "__main__":
    main()
