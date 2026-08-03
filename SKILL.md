---
name: product-white-background-retouch
description: Retouch eyewear and other product photos into the approved white-background style while preserving the complete frame silhouette, lenses, translucent parts, nose pads, logos, text, geometry, and colour. Use for 白底图精修, 眼镜白底图, 产品抠图, 去背景, 修白底, 批量白底图, 镜片去倒影, or requests to repair lens reflections. Reuse an exact approved same-stem asset first; otherwise build a contrast-enhanced guidance image for complete-shape masking, composite original pixels, and optionally repair only the lens interior with local AI editing.
---

# White-Background Product Retouch

Use the approved **first-version mode** by default:

- pure white canvas;
- original frame colour and lens tint;
- intact translucent material, nose pads, rimless lens edges, logos, and text;
- only a narrow, soft contact shadow;
- no full-object glow, hard halo, or generative redrawing.

## Complete-Shape Masking

For every new image, follow this order:

1. Create a contrast-enhanced guidance image for segmentation only.
2. Confirm the guidance image reveals the complete top rim, lower rim, bridge, hinges, temple tips, nose pads, and transparent edges.
3. Generate and refine the subject mask from the guidance image.
4. Composite the untouched original pixels through the verified mask onto white.

Never apply the contrast adjustment to the final product pixels. It exists only to help the mask detect pale or translucent material.

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

When no exact approved asset exists, the wrapper runs contrast-guided cutout. Keep the original size and product pixels; do not resize, redraw, recolour, sharpen, or regenerate the frame.

For translucent, gradient-lens, rimless, or semi-rimless eyewear:

1. Prefer the default `--fallback-mode cutout` with contrast guidance.
2. Inspect the guidance image, raw mask, and refined mask before accepting the output.
3. Increase `--mask-contrast` or `--mask-expand` slightly when the frame is incomplete.
4. Increase `--mask-low` or reduce `--mask-feather` when a broad halo remains.
5. Preserve a small contact shadow only when it stays directly below the product.

Use `--fallback-mode background` only when contrast-guided cutout still cannot preserve a difficult transparent component.

## Lens Reflection Repair

Perform AI reflection repair only after the product cutout is approved. Read `references/lens-ai-repair.md` before editing.

Keep the AI edit inside a feathered lens-interior mask. Never include the frame, hinges, bridge, nose pads, logos, or lens edge in the edit mask. Composite the repaired lens patch back onto the non-generative retouch; never replace the full image with an AI redraw.

## Required QA

Always inspect the full output and a close crop around the bridge, nose pads, lens edges, and temple tips.

Reject or locally refine the result when any of these appear:

- missing lens or nose-pad pixels;
- white holes inside a lens;
- gray background trapped in frame openings;
- jagged debris below the lens;
- large glow or detached shadow;
- changed frame colour, lens gradient, logo, text, angle, or geometry.
- AI-smoothed lens edges or altered frame thickness.

Confirm the corner pixel is pure white and report the final absolute output path.
