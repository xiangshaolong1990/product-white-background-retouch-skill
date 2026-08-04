#!/usr/bin/env python3
"""Isolate a product onto pure white with no shadow or a minimal contact shadow."""

from __future__ import annotations

import argparse
from collections import deque
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageEnhance, ImageFilter, ImageOps


SCRIPT_DIR = Path(__file__).resolve().parent
VISION_SOURCE = SCRIPT_DIR / "vision_subject_mask.swift"
ALPHA_MATTING_SCRIPT = SCRIPT_DIR / "alpha_matte_cutout.py"
ALPHA_MATTING_VENV = (
    Path.home()
    / ".cache"
    / "codex-product-white-background-retouch"
    / "alpha-matting-venv"
    / "bin"
    / "python"
)


def corner_background_colors(image: Image.Image, sample_size: int) -> list[tuple[int, int, int]]:
    """Estimate the background from small samples in all four corners."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    sample_width = min(sample_size, width)
    sample_height = min(sample_size, height)
    positions = (
        (0, 0),
        (width - sample_width, 0),
        (0, height - sample_height),
        (width - sample_width, height - sample_height),
    )

    colors: list[tuple[int, int, int]] = []
    for left, top in positions:
        sample = rgb.crop((left, top, left + sample_width, top + sample_height))
        colors.append(
            tuple(round(value) for value in sample.resize((1, 1), Image.Resampling.BOX).getpixel((0, 0)))
        )
    return colors


def background_mask(
    image: Image.Image,
    sample_size: int,
    min_luminance: int,
    max_chroma: int,
    max_distance: int,
    neutral_shadow_luminance: int,
    neutral_shadow_chroma: int,
) -> Image.Image:
    """Select corner-connected studio background and optional neutral shadows."""
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    references = corner_background_colors(rgb, sample_size)

    def is_background(color: tuple[int, int, int]) -> bool:
        red, green, blue = color
        luminance = (299 * red + 587 * green + 114 * blue) // 1000
        chroma = max(color) - min(color)
        if (
            neutral_shadow_luminance > 0
            and luminance >= neutral_shadow_luminance
            and chroma <= neutral_shadow_chroma
        ):
            return True
        if luminance < min_luminance or chroma > max_chroma:
            return False
        # A summed RGB distance can leak into pale, transparent product parts.
        # Preserve any pixel that differs noticeably from the corner backdrop.
        return min(
            max(
                abs(red - reference[0]),
                abs(green - reference[1]),
                abs(blue - reference[2]),
            )
            for reference in references
        ) <= max_distance

    mask = Image.new("L", (width, height), 0)
    mask_pixels = mask.load()
    queue: deque[tuple[int, int]] = deque()

    for x, y in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        if is_background(pixels[x, y]):
            mask_pixels[x, y] = 255
            queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (
                0 <= next_x < width
                and 0 <= next_y < height
                and mask_pixels[next_x, next_y] == 0
                and is_background(pixels[next_x, next_y])
            ):
                mask_pixels[next_x, next_y] = 255
                queue.append((next_x, next_y))

    return mask


def clear_isolated_protected_specks(
    mask: Image.Image,
    minimum_component_pixels: int,
) -> tuple[Image.Image, int, int]:
    """Remove tiny protected islands left behind by dust or sensor specks."""
    if minimum_component_pixels <= 1:
        return mask, 0, 0

    width, height = mask.size
    total_pixels = width * height
    values = bytearray(mask.tobytes())
    visited = bytearray(total_pixels)
    cleared_components = 0
    cleared_pixels = 0

    for start in range(total_pixels):
        if values[start] != 0 or visited[start]:
            continue

        queue: deque[int] = deque((start,))
        visited[start] = 1
        members = [start]
        is_large_component = False

        while queue:
            current = queue.popleft()
            x = current % width
            neighbors: list[int] = []
            if current >= width:
                neighbors.append(current - width)
            if current + width < total_pixels:
                neighbors.append(current + width)
            if x:
                neighbors.append(current - 1)
            if x + 1 < width:
                neighbors.append(current + 1)

            for neighbor in neighbors:
                if values[neighbor] != 0 or visited[neighbor]:
                    continue
                visited[neighbor] = 1
                queue.append(neighbor)
                if not is_large_component:
                    members.append(neighbor)
                    if len(members) >= minimum_component_pixels:
                        is_large_component = True
                        members.clear()

        if not is_large_component:
            for member in members:
                values[member] = 255
            cleared_components += 1
            cleared_pixels += len(members)

    cleaned_mask = Image.frombytes("L", mask.size, bytes(values))
    return cleaned_mask, cleared_components, cleared_pixels


def apply_white_background(image: Image.Image, mask: Image.Image) -> Image.Image:
    white = Image.new("RGBA", image.size, (255, 255, 255, 255))
    return Image.composite(white, image.convert("RGBA"), mask)


def compile_vision_helper() -> Path:
    """Compile the local macOS Vision foreground-mask helper when needed."""
    if platform.system() != "Darwin":
        raise RuntimeError("Cutout mode requires macOS Vision; use --mode background on other systems")
    if not VISION_SOURCE.is_file():
        raise RuntimeError(f"Vision helper source not found: {VISION_SOURCE}")

    compiler = shutil.which("swiftc")
    if compiler is None:
        xcrun = shutil.which("xcrun")
        if xcrun is None:
            raise RuntimeError("Swift compiler not found; install Apple Command Line Tools")
        result = subprocess.run(
            [xcrun, "--find", "swiftc"],
            check=True,
            capture_output=True,
            text=True,
        )
        compiler = result.stdout.strip()

    cache_dir = Path.home() / ".cache" / "codex-product-white-background-retouch"
    cache_dir.mkdir(parents=True, exist_ok=True)
    binary = cache_dir / "vision_subject_mask"
    if not binary.is_file() or binary.stat().st_mtime_ns < VISION_SOURCE.stat().st_mtime_ns:
        subprocess.run(
            [compiler, "-O", str(VISION_SOURCE), "-o", str(binary)],
            check=True,
        )
    return binary


def vision_subject_mask(image: Image.Image) -> Image.Image:
    """Use macOS Vision to isolate the product and exclude its original shadow."""
    helper = compile_vision_helper()
    with tempfile.TemporaryDirectory(prefix="product-cutout-") as temporary_directory:
        temporary = Path(temporary_directory)
        normalized_input = temporary / "input.jpg"
        mask_output = temporary / "subject-mask.png"
        image.convert("RGB").save(normalized_input, "JPEG", quality=92, subsampling=0)
        subprocess.run(
            [str(helper), str(normalized_input), str(mask_output)],
            check=True,
        )
        mask = Image.open(mask_output).convert("L").copy()
    if mask.size != image.size:
        raise RuntimeError(f"Vision mask size {mask.size} does not match source {image.size}")
    if mask.getbbox() is None:
        raise RuntimeError("Vision did not detect a foreground product")
    return mask


def contrast_guidance_image(
    image: Image.Image,
    autocontrast_cutoff: int,
    contrast: float,
) -> Image.Image:
    """Reveal pale product boundaries for segmentation without changing output pixels."""
    guidance = ImageOps.autocontrast(
        image.convert("RGB"),
        cutoff=max(0, min(20, autocontrast_cutoff)),
    )
    return ImageEnhance.Contrast(guidance).enhance(max(0.1, contrast))


def refine_subject_mask(
    mask: Image.Image,
    low: int,
    high: int,
    expand: int,
    feather: float,
) -> Image.Image:
    """Complete the subject silhouette, then suppress broad soft-mask halos."""
    low = max(0, min(254, low))
    high = max(low + 1, min(255, high))
    refined = mask.convert("L")
    if expand > 0:
        radius = max(1, min(20, expand)) * 2 + 1
        refined = refined.filter(ImageFilter.MaxFilter(radius))
    refined = refined.point(
        lambda value: (
            0
            if value <= low
            else 255
            if value >= high
            else round((value - low) * 255 / (high - low))
        )
    )
    if feather > 0:
        refined = refined.filter(ImageFilter.GaussianBlur(min(5.0, feather)))
    return refined


def alpha_python_candidates(explicit: Path | None) -> list[Path]:
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit.expanduser())
    environment_python = os.environ.get("PRODUCT_RETOUCH_ALPHA_PYTHON")
    if environment_python:
        candidates.append(Path(environment_python).expanduser())
    candidates.extend((ALPHA_MATTING_VENV, Path(sys.executable)))
    return candidates


def find_alpha_python(explicit: Path | None) -> Path | None:
    seen: set[Path] = set()
    for candidate in alpha_python_candidates(explicit):
        candidate = candidate.expanduser().absolute()
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        result = subprocess.run(
            [str(candidate), "-c", "import numpy, scipy, pymatting, PIL"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return candidate
    return None


def alpha_matte_cutout(
    input_path: Path,
    raw_subject_mask: Image.Image,
    alpha_python: Path,
    foreground_threshold: int,
    background_threshold: int,
    foreground_erode: int,
    background_erode: int,
    margin: int,
    max_matte_side: int,
    debug_alpha_mask: Path | None,
    debug_trimap: Path | None,
) -> Image.Image:
    if not ALPHA_MATTING_SCRIPT.is_file():
        raise RuntimeError(f"Alpha matting helper not found: {ALPHA_MATTING_SCRIPT}")
    with tempfile.TemporaryDirectory(prefix="product-alpha-matting-") as temporary_directory:
        temporary = Path(temporary_directory)
        mask_path = temporary / "raw-subject-mask.png"
        cutout_path = temporary / "cutout.png"
        raw_subject_mask.save(mask_path, "PNG")
        command = [
            str(alpha_python),
            str(ALPHA_MATTING_SCRIPT),
            "--input",
            str(input_path),
            "--mask",
            str(mask_path),
            "--output",
            str(cutout_path),
            "--foreground-threshold",
            str(foreground_threshold),
            "--background-threshold",
            str(background_threshold),
            "--foreground-erode",
            str(foreground_erode),
            "--background-erode",
            str(background_erode),
            "--margin",
            str(margin),
            "--max-matte-side",
            str(max_matte_side),
        ]
        if debug_alpha_mask:
            command.extend(("--debug-alpha-mask", str(debug_alpha_mask)))
        if debug_trimap:
            command.extend(("--debug-trimap", str(debug_trimap)))
        subprocess.run(command, check=True)
        return Image.open(cutout_path).convert("RGBA").copy()


def subtle_contact_shadow(
    subject_mask: Image.Image,
    radius: int,
    opacity: int,
    offset: int,
) -> Image.Image:
    """Create a narrow shadow only below the detected subject bottom edge."""
    width, height = subject_mask.size
    contact = Image.new("L", subject_mask.size, 0)
    source_pixels = subject_mask.load()
    contact_pixels = contact.load()
    bounds = subject_mask.getbbox()
    if bounds is None:
        return contact

    left, top, right, bottom = bounds
    thickness = max(2, radius // 3)
    for x in range(left, right):
        for y in range(bottom - 1, top - 1, -1):
            if source_pixels[x, y] >= 128:
                start = min(height - 1, y + offset)
                stop = min(height, start + thickness)
                for shadow_y in range(start, stop):
                    contact_pixels[x, shadow_y] = 255
                break

    blurred = contact.filter(ImageFilter.GaussianBlur(max(1, radius)))
    scale = max(0, min(255, opacity))
    return blurred.point(lambda value: value * scale // 255)


def apply_cutout_background(
    image: Image.Image,
    subject_mask: Image.Image,
    shadow: str,
    shadow_radius: int,
    shadow_opacity: int,
    shadow_offset: int,
) -> Image.Image:
    """Composite the detected product on white with no shadow or a tiny contact shadow."""
    white = Image.new("RGBA", image.size, (255, 255, 255, 255))
    if shadow == "subtle":
        shadow_alpha = subtle_contact_shadow(
            subject_mask,
            shadow_radius,
            shadow_opacity,
            shadow_offset,
        )
        black = Image.new("RGBA", image.size, (0, 0, 0, 255))
        white = Image.composite(black, white, shadow_alpha)
    return Image.composite(image.convert("RGBA"), white, subject_mask)


def apply_rgba_cutout_background(
    cutout: Image.Image,
    subject_mask: Image.Image,
    shadow: str,
    shadow_radius: int,
    shadow_opacity: int,
    shadow_offset: int,
) -> Image.Image:
    white = Image.new("RGBA", cutout.size, (255, 255, 255, 255))
    if shadow == "subtle":
        shadow_alpha = subtle_contact_shadow(
            subject_mask,
            shadow_radius,
            shadow_opacity,
            shadow_offset,
        )
        black = Image.new("RGBA", cutout.size, (0, 0, 0, 255))
        white = Image.composite(black, white, shadow_alpha)
    return Image.alpha_composite(white, cutout.convert("RGBA"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Source product image")
    parser.add_argument("--output", type=Path, required=True, help="Output PNG path")
    parser.add_argument(
        "--mode",
        choices=("cutout", "background"),
        default="cutout",
        help="cutout isolates the product and removes source shadows; background keeps the legacy conservative cleanup",
    )
    parser.add_argument(
        "--shadow",
        choices=("none", "subtle"),
        default="none",
        help="Optional narrow contact shadow in cutout mode",
    )
    parser.add_argument("--shadow-radius", type=int, default=12)
    parser.add_argument("--shadow-opacity", type=int, default=18)
    parser.add_argument("--shadow-offset", type=int, default=6)
    parser.add_argument(
        "--mask-guide",
        choices=("contrast", "original"),
        default="contrast",
        help="Build the subject mask from a contrast guide or the untouched source",
    )
    parser.add_argument("--mask-contrast", type=float, default=1.35)
    parser.add_argument("--mask-autocontrast-cutoff", type=int, default=1)
    parser.add_argument("--mask-low", type=int, default=78)
    parser.add_argument("--mask-high", type=int, default=184)
    parser.add_argument("--mask-expand", type=int, default=1)
    parser.add_argument("--mask-feather", type=float, default=0.8)
    parser.add_argument(
        "--edge-mode",
        choices=("alpha", "binary"),
        default="alpha",
        help="Use trimap-based alpha matting for translucent edges or the legacy binary mask",
    )
    parser.add_argument(
        "--alpha-fallback",
        choices=("binary", "error"),
        default="binary",
        help="Behavior when the optional PyMatting runtime is unavailable",
    )
    parser.add_argument("--alpha-python", type=Path)
    parser.add_argument("--alpha-foreground-threshold", type=int, default=235)
    parser.add_argument("--alpha-background-threshold", type=int, default=5)
    parser.add_argument("--alpha-foreground-erode", type=int, default=7)
    parser.add_argument("--alpha-background-erode", type=int, default=25)
    parser.add_argument("--alpha-margin", type=int, default=70)
    parser.add_argument("--alpha-max-matte-side", type=int, default=3000)
    parser.add_argument("--debug-guidance-image", type=Path)
    parser.add_argument("--debug-raw-subject-mask", type=Path)
    parser.add_argument("--debug-subject-mask", type=Path, help="Optional detected-subject mask PNG")
    parser.add_argument("--debug-alpha-mask", type=Path)
    parser.add_argument("--debug-trimap", type=Path)
    parser.add_argument("--debug-background-mask", type=Path, help="Optional connected-background mask PNG")
    parser.add_argument("--corner-sample", type=int, default=32)
    parser.add_argument("--min-luminance", type=int, default=180)
    parser.add_argument("--max-chroma", type=int, default=7)
    parser.add_argument("--max-distance", type=int, default=24)
    parser.add_argument(
        "--neutral-shadow-luminance",
        type=int,
        default=0,
        help="Also whiten corner-connected neutral studio shadows at or above this luminance; 0 disables",
    )
    parser.add_argument(
        "--neutral-shadow-chroma",
        type=int,
        default=7,
        help="Maximum chroma for optional neutral shadow cleanup",
    )
    parser.add_argument(
        "--min-protected-component",
        type=int,
        default=24,
        help="Whiten disconnected protected components smaller than this many pixels; use 0 to disable",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input file not found: {args.input}")

    original = ImageOps.exif_transpose(Image.open(args.input)).convert("RGBA")
    cleared_components = 0
    cleared_pixels = 0
    raw_subject_mask: Image.Image | None = None
    guidance: Image.Image | None = None
    if args.mode == "cutout":
        guidance = (
            contrast_guidance_image(
                original,
                args.mask_autocontrast_cutoff,
                args.mask_contrast,
            )
            if args.mask_guide == "contrast"
            else original.convert("RGB")
        )
        raw_subject_mask = vision_subject_mask(guidance)
        alpha_python = find_alpha_python(args.alpha_python) if args.edge_mode == "alpha" else None
        if args.edge_mode == "alpha" and alpha_python is None and args.alpha_fallback == "error":
            raise RuntimeError(
                "PyMatting runtime not found. Run scripts/setup_alpha_matting.py or use --edge-mode binary"
            )
        if alpha_python is not None:
            cutout = alpha_matte_cutout(
                args.input,
                raw_subject_mask,
                alpha_python,
                args.alpha_foreground_threshold,
                args.alpha_background_threshold,
                args.alpha_foreground_erode,
                args.alpha_background_erode,
                args.alpha_margin,
                args.alpha_max_matte_side,
                args.debug_alpha_mask,
                args.debug_trimap,
            )
            subject_mask = cutout.getchannel("A")
            retouched = apply_rgba_cutout_background(
                cutout,
                subject_mask,
                args.shadow,
                args.shadow_radius,
                args.shadow_opacity,
                args.shadow_offset,
            )
            active_edge_mode = "alpha"
        else:
            if args.edge_mode == "alpha":
                print("Alpha matting runtime unavailable; falling back to binary mask")
            subject_mask = refine_subject_mask(
                raw_subject_mask,
                args.mask_low,
                args.mask_high,
                args.mask_expand,
                args.mask_feather,
            )
            retouched = apply_cutout_background(
                original,
                subject_mask,
                args.shadow,
                args.shadow_radius,
                args.shadow_opacity,
                args.shadow_offset,
            )
            active_edge_mode = "binary"
        mask = ImageOps.invert(subject_mask)
    else:
        mask = background_mask(
            original,
            args.corner_sample,
            args.min_luminance,
            args.max_chroma,
            args.max_distance,
            args.neutral_shadow_luminance,
            args.neutral_shadow_chroma,
        )
        mask, cleared_components, cleared_pixels = clear_isolated_protected_specks(
            mask,
            args.min_protected_component,
        )
        subject_mask = ImageOps.invert(mask)
        retouched = apply_white_background(original, mask)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    retouched.convert("RGB").save(args.output, "PNG", compress_level=1)
    if args.debug_subject_mask:
        args.debug_subject_mask.parent.mkdir(parents=True, exist_ok=True)
        subject_mask.save(args.debug_subject_mask, "PNG", compress_level=1)
    if args.debug_raw_subject_mask and raw_subject_mask is not None:
        args.debug_raw_subject_mask.parent.mkdir(parents=True, exist_ok=True)
        raw_subject_mask.save(args.debug_raw_subject_mask, "PNG", compress_level=1)
    if args.debug_guidance_image and guidance is not None:
        args.debug_guidance_image.parent.mkdir(parents=True, exist_ok=True)
        guidance.save(args.debug_guidance_image, "PNG", compress_level=1)
    if args.debug_background_mask:
        args.debug_background_mask.parent.mkdir(parents=True, exist_ok=True)
        mask.save(args.debug_background_mask, "PNG", compress_level=1)

    background_pixels = sum(mask.histogram()[1:])
    print(f"Saved: {args.output}")
    print(f"Mode: {args.mode}; shadow: {args.shadow}")
    if args.mode == "cutout":
        print(
            "Mask guidance: "
            f"{args.mask_guide}; contrast={args.mask_contrast}; "
            f"range={args.mask_low}-{args.mask_high}; expand={args.mask_expand}"
        )
        print(f"Edge mode: {active_edge_mode}")
    print(f"Source size: {original.size}; output size: {retouched.size}")
    print(f"Background pixels changed: {background_pixels}")
    print(f"Isolated protected components cleared: {cleared_components}")
    print(f"Isolated protected pixels cleared: {cleared_pixels}")


if __name__ == "__main__":
    main()
