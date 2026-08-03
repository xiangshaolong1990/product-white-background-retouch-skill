---
name: product-white-background-retouch
description: Retouch eyewear and other product photos into the approved first-version white-background style while preserving lenses, translucent frames, nose pads, logos, text, geometry, and colour. Use for 白底图精修, 眼镜白底图, 产品抠图, 去背景, 修白底, 批量白底图, or requests to match the previously approved natural white-background look with only a small contact shadow. Reuse an exact approved same-stem asset first for speed; otherwise use conservative background cleanup and mandatory visual QA.
---

# White-Background Product Retouch

Use the approved **first-version mode** by default:

- pure white canvas;
- original frame colour and lens tint;
- intact translucent material, nose pads, rimless lens edges, logos, and text;
- only a narrow, soft contact shadow;
- no full-object glow, hard halo, or generative redrawing.

## Fast Path

Run:

```bash
SKILL_ROOT="${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch"
python3 "$SKILL_ROOT/scripts/first_mode_retouch.py" \
  --input "/absolute/path/IMG_0001.JPG"
```

The script first checks for an exact approved same-stem asset such as:

```text
/absolute/path/白底/IMG_0001-1.png
```

When found, copy it directly to `IMG_0001修_第一版模式.png`. This is the preferred fast path because it preserves the user-approved retouch exactly and avoids repeated masking.

Use `--approved /absolute/path/reference.png` to select an explicit approved asset. Use `--force-process` only when the approved asset must be ignored.

## New-Image Path

When no exact approved asset exists, the wrapper runs the conservative background workflow. Keep the original size and product pixels; do not resize, redraw, recolour, sharpen, or regenerate the product.

For translucent, gradient-lens, rimless, or semi-rimless eyewear:

1. Prefer `--fallback-mode background`.
2. Keep the original lens interiors and translucent frame material.
3. Preserve a small amount of source contact shadow only when it remains narrow and natural.
4. Do not use Vision cutout as the default; it can treat pale lenses or nose pads as background.

Use `--fallback-mode cutout` only for opaque products with clearly separated edges.

## Required QA

Always inspect the full output and a close crop around the bridge, nose pads, lens edges, and temple tips.

Reject or locally refine the result when any of these appear:

- missing lens or nose-pad pixels;
- white holes inside a lens;
- gray background trapped in frame openings;
- jagged debris below the lens;
- large glow or detached shadow;
- changed frame colour, lens gradient, logo, text, angle, or geometry.

Confirm the corner pixel is pure white and report the final absolute output path.
