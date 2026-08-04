#!/usr/bin/env python3
"""Refine a coarse product mask into an alpha-matted RGBA cutout."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from pymatting.alpha.estimate_alpha_cf import estimate_alpha_cf
from pymatting.foreground.estimate_foreground_ml import estimate_foreground_ml
from scipy.ndimage import binary_erosion


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--mask", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--foreground-threshold", type=int, default=235)
    parser.add_argument("--background-threshold", type=int, default=5)
    parser.add_argument("--foreground-erode", type=int, default=7)
    parser.add_argument("--background-erode", type=int, default=25)
    parser.add_argument("--margin", type=int, default=70)
    parser.add_argument(
        "--max-matte-side",
        type=int,
        default=3000,
        help="Solve alpha on a reduced tight crop, then restore the original-size core pixels",
    )
    parser.add_argument("--core-preserve-threshold", type=float, default=0.995)
    parser.add_argument("--debug-alpha-mask", type=Path)
    parser.add_argument("--debug-trimap", type=Path)
    return parser.parse_args()


def erosion_structure(size: int) -> np.ndarray:
    size = max(1, min(101, size))
    if size % 2 == 0:
        size += 1
    return np.ones((size, size), dtype=np.uint8)


def resize_rgb(array: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    image = Image.fromarray(np.round(np.clip(array, 0.0, 1.0) * 255).astype(np.uint8))
    return np.asarray(image.resize(size, Image.Resampling.LANCZOS)).astype(np.float64) / 255.0


def resize_mask(array: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    image = Image.fromarray(array.astype(np.uint8))
    return np.asarray(image.resize(size, Image.Resampling.BILINEAR))


def resize_float(array: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    image = Image.fromarray(array.astype(np.float32))
    return np.asarray(image.resize(size, Image.Resampling.LANCZOS)).astype(np.float64)


def main() -> None:
    args = parse_args()
    image = ImageOps.exif_transpose(Image.open(args.input)).convert("RGB")
    mask = Image.open(args.mask).convert("L")
    if mask.size != image.size:
        raise SystemExit(f"Mask size {mask.size} does not match image size {image.size}")

    image_array = np.asarray(image).astype(np.float64) / 255.0
    mask_array = np.asarray(mask)
    support_y, support_x = np.nonzero(mask_array > 0)
    if support_x.size == 0:
        raise SystemExit("The coarse mask contains no foreground support")

    margin = max(0, min(500, args.margin))
    left = max(0, int(support_x.min()) - margin)
    top = max(0, int(support_y.min()) - margin)
    right = min(image.width, int(support_x.max()) + margin + 1)
    bottom = min(image.height, int(support_y.max()) + margin + 1)
    crop_image = image_array[top:bottom, left:right]
    crop_mask = mask_array[top:bottom, left:right]
    crop_height, crop_width = crop_mask.shape

    max_matte_side = max(0, args.max_matte_side)
    matte_scale = 1.0
    if max_matte_side and max(crop_width, crop_height) > max_matte_side:
        matte_scale = max_matte_side / max(crop_width, crop_height)
    matte_width = max(64, round(crop_width * matte_scale))
    matte_height = max(64, round(crop_height * matte_scale))
    matte_size = (matte_width, matte_height)
    matte_image = resize_rgb(crop_image, matte_size) if matte_scale < 1.0 else crop_image
    matte_mask = resize_mask(crop_mask, matte_size) if matte_scale < 1.0 else crop_mask

    foreground_threshold = max(1, min(255, args.foreground_threshold))
    background_threshold = max(0, min(foreground_threshold - 1, args.background_threshold))
    sure_foreground = binary_erosion(
        matte_mask > foreground_threshold,
        structure=erosion_structure(round(args.foreground_erode * matte_scale)),
        border_value=0,
    )
    sure_background = binary_erosion(
        matte_mask < background_threshold,
        structure=erosion_structure(round(args.background_erode * matte_scale)),
        border_value=0,
    )
    if not np.any(sure_foreground):
        raise SystemExit("Alpha trimap has no sure foreground pixels")
    if not np.any(sure_background):
        raise SystemExit("Alpha trimap has no sure background pixels")

    trimap = np.full(matte_mask.shape, 0.5, dtype=np.float64)
    trimap[sure_background] = 0.0
    trimap[sure_foreground] = 1.0
    alpha = np.clip(estimate_alpha_cf(matte_image, trimap), 0.0, 1.0)
    foreground = np.clip(estimate_foreground_ml(matte_image, alpha), 0.0, 1.0)

    if matte_scale < 1.0:
        alpha = np.clip(resize_float(alpha, (crop_width, crop_height)), 0.0, 1.0)
        foreground = resize_rgb(foreground, (crop_width, crop_height))

    core_threshold = max(0.9, min(1.0, args.core_preserve_threshold))
    core = binary_erosion(
        crop_mask > foreground_threshold,
        structure=erosion_structure(args.foreground_erode),
        border_value=0,
    )
    preserve = core & (alpha >= core_threshold)
    foreground[preserve] = crop_image[preserve]

    rgba = np.zeros((image.height, image.width, 4), dtype=np.uint8)
    rgba_crop = rgba[top:bottom, left:right]
    rgba_crop[..., :3] = np.round(foreground * 255).astype(np.uint8)
    rgba_crop[..., 3] = np.round(alpha * 255).astype(np.uint8)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba).save(args.output, "PNG", compress_level=1)

    if args.debug_alpha_mask:
        alpha_canvas = np.zeros(mask_array.shape, dtype=np.uint8)
        alpha_canvas[top:bottom, left:right] = np.round(alpha * 255).astype(np.uint8)
        args.debug_alpha_mask.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(alpha_canvas).save(args.debug_alpha_mask, "PNG", compress_level=1)

    if args.debug_trimap:
        trimap_canvas = np.zeros(mask_array.shape, dtype=np.uint8)
        debug_trimap = (
            resize_mask(np.round(trimap * 255).astype(np.uint8), (crop_width, crop_height))
            if matte_scale < 1.0
            else np.round(trimap * 255).astype(np.uint8)
        )
        trimap_canvas[top:bottom, left:right] = debug_trimap
        args.debug_trimap.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(trimap_canvas).save(args.debug_trimap, "PNG", compress_level=1)

    unknown_pixels = int(np.count_nonzero((trimap > 0.0) & (trimap < 1.0)))
    print(
        f"Alpha crop: {right - left}x{bottom - top}; "
        f"matte: {matte_width}x{matte_height}; unknown pixels: {unknown_pixels}"
    )


if __name__ == "__main__":
    main()
