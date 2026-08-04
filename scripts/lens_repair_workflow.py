#!/usr/bin/env python3
"""Prepare a local lens-defect crop for AI editing, then composite the result safely."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps


def canvas_size(width: int, height: int) -> tuple[int, int]:
    ratio = width / max(1, height)
    if ratio > 1.2:
        return 1536, 1024
    if ratio < 0.83:
        return 1024, 1536
    return 1024, 1024


def polygon_mask(size: tuple[int, int], value: str, feather: float) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for raw_polygon in value.split(";"):
        points: list[tuple[int, int]] = []
        for raw_point in raw_polygon.strip().split():
            x_text, y_text = raw_point.split(",", 1)
            points.append((int(x_text), int(y_text)))
        if len(points) < 3:
            raise SystemExit("Each repair polygon needs at least three points")
        draw.polygon(points, fill=255)
    if feather > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(min(30.0, feather)))
    return mask


def prepare(args: argparse.Namespace) -> None:
    source = ImageOps.exif_transpose(Image.open(args.input)).convert("RGB")
    if args.mask:
        repair_mask = Image.open(args.mask).convert("L")
    elif args.polygons:
        repair_mask = polygon_mask(source.size, args.polygons, args.feather)
    else:
        raise SystemExit("Provide --mask or --polygons")
    if repair_mask.size != source.size:
        raise SystemExit(f"Repair mask size {repair_mask.size} does not match image size {source.size}")
    support = repair_mask.point(lambda value: 255 if value > 3 else 0).getbbox()
    if support is None:
        raise SystemExit("Repair mask is empty")

    margin = max(0, min(500, args.crop_margin))
    left = max(0, support[0] - margin)
    top = max(0, support[1] - margin)
    right = min(source.width, support[2] + margin)
    bottom = min(source.height, support[3] + margin)
    crop = source.crop((left, top, right, bottom))
    crop_mask = repair_mask.crop((left, top, right, bottom))

    target_size = canvas_size(*crop.size)
    scale = min(target_size[0] / crop.width, target_size[1] / crop.height)
    fit_size = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
    offset = ((target_size[0] - fit_size[0]) // 2, (target_size[1] - fit_size[1]) // 2)

    input_canvas = Image.new("RGB", target_size, "white")
    input_canvas.paste(crop.resize(fit_size, Image.Resampling.LANCZOS), offset)
    mask_canvas = Image.new("L", target_size, 0)
    mask_canvas.paste(crop_mask.resize(fit_size, Image.Resampling.LANCZOS), offset)

    args.work_dir.mkdir(parents=True, exist_ok=True)
    repair_mask.save(args.work_dir / "full-mask.png", "PNG", compress_level=1)
    input_canvas.save(args.work_dir / "input.png", "PNG", compress_level=1)
    mask_canvas.save(args.work_dir / "mask.png", "PNG", compress_level=1)
    manifest = {
        "source_size": list(source.size),
        "crop": [left, top, right, bottom],
        "target_size": list(target_size),
        "fit_size": list(fit_size),
        "offset": list(offset),
    }
    (args.work_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Prepared: {args.work_dir}")


def composite(args: argparse.Namespace) -> None:
    source = ImageOps.exif_transpose(Image.open(args.input)).convert("RGB")
    mask_path = args.mask or args.manifest.parent / "full-mask.png"
    repair_mask = Image.open(mask_path).convert("L")
    if args.protect_mask:
        protect_mask = Image.open(args.protect_mask).convert("L")
        if protect_mask.size != source.size:
            raise SystemExit(
                f"Protect mask size {protect_mask.size} does not match image size {source.size}"
            )
        repair_mask = ImageChops.multiply(repair_mask, ImageOps.invert(protect_mask))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if repair_mask.size != source.size or tuple(manifest["source_size"]) != source.size:
        raise SystemExit("Source, mask, and manifest dimensions do not match")

    left, top, right, bottom = manifest["crop"]
    target_size = tuple(manifest["target_size"])
    fit_width, fit_height = manifest["fit_size"]
    offset_x, offset_y = manifest["offset"]
    edited_canvas = Image.open(args.ai_result).convert("RGB").resize(
        target_size,
        Image.Resampling.LANCZOS,
    )
    fitted = edited_canvas.crop(
        (offset_x, offset_y, offset_x + fit_width, offset_y + fit_height)
    )
    crop_size = (right - left, bottom - top)
    repaired_crop = fitted.resize(crop_size, Image.Resampling.LANCZOS)
    original_crop = source.crop((left, top, right, bottom))
    crop_mask = repair_mask.crop((left, top, right, bottom))
    final_crop = Image.composite(repaired_crop, original_crop, crop_mask)
    final = source.copy()
    final.paste(final_crop, (left, top))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    final.save(args.output, "PNG", compress_level=1)
    print(f"Saved: {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--input", type=Path, required=True)
    prepare_parser.add_argument("--mask", type=Path)
    prepare_parser.add_argument(
        "--polygons",
        help='Semicolon-separated full-size polygons, for example "x,y x,y x,y;x,y x,y x,y"',
    )
    prepare_parser.add_argument("--feather", type=float, default=6.0)
    prepare_parser.add_argument("--work-dir", type=Path, required=True)
    prepare_parser.add_argument("--crop-margin", type=int, default=80)
    prepare_parser.set_defaults(func=prepare)

    composite_parser = subparsers.add_parser("composite")
    composite_parser.add_argument("--input", type=Path, required=True)
    composite_parser.add_argument("--mask", type=Path)
    composite_parser.add_argument(
        "--protect-mask",
        type=Path,
        help="Full-size soft mask whose white pixels must come from the original source",
    )
    composite_parser.add_argument("--manifest", type=Path, required=True)
    composite_parser.add_argument("--ai-result", type=Path, required=True)
    composite_parser.add_argument("--output", type=Path, required=True)
    composite_parser.set_defaults(func=composite)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
