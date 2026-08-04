---
name: product-white-background-retouch
description: Retouch eyewear and other product photos into the approved white-background style while preserving the complete frame silhouette, lenses, translucent parts, nose pads, logos, text, geometry, and colour. Use for 白底图精修, 眼镜白底图, 产品抠图, 去背景, 修白底, 批量白底图, 镜片去倒影, or requests to repair lens reflections. Reuse an exact approved same-stem background asset first; otherwise build a contrast-enhanced coarse mask and refine translucent edges with trimap-based alpha matting. For eyewear, mandatory lens inspection decides whether a small local AI repair is needed; clean natural lenses must retain their original pixels.
---

# White-Background Product Retouch

Use the approved **final-only mode** by default:

- pure white canvas;
- original frame colour and lens tint;
- intact translucent material, nose pads, rimless lens edges, logos, and text;
- reflection-free lens surfaces with smooth original tint gradients and intact through-lens temple perspective;
- no shadow unless the user explicitly asks for a subtle contact shadow;
- no full-object glow, hard halo, or generative redrawing.
- only one final image in the delivery folder; keep masks, crops, and diagnostics in a temporary directory.

## Complete-Shape Masking

For every new image, follow this order:

1. Create a contrast-enhanced guidance image for segmentation only.
2. Confirm the guidance image reveals the complete top rim, lower rim, bridge, hinges, temple tips, nose pads, and transparent edges.
3. Generate a coarse soft subject mask from the guidance image.
4. Build a trimap and use Alpha Matting to recover translucent outer-frame pixels.
5. Preserve untouched original pixels in the sure-foreground core and composite only the estimated translucent edge onto white.

Never apply the contrast adjustment to the final product pixels. It exists only to help the mask detect pale or translucent material.

## Fast Path

Run:

```bash
SKILL_ROOT="${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch"
python3 "$SKILL_ROOT/scripts/final_white_background_retouch.py" \
  --input "/absolute/path/IMG_0001.JPG"
```

The script first checks for an exact approved same-stem asset such as:

```text
/absolute/path/白底/IMG_0001-1.png
```

When found, reuse it only as the white-background base. For eyewear, this never bypasses mandatory lens inspection and dual-lens QA. Apply AI repair only when an identifiable defect is present. Deliver only `IMG_0001修.png` after the lens-quality gate passes.

Use `--approved /absolute/path/reference.png` to select an explicit approved asset. Use `--force-process` only when the approved asset must be ignored.

## New-Image Path

When no exact approved asset exists, the wrapper runs contrast-guided cutout plus Alpha Matting. Keep the original size and product pixels; do not resize, redraw, recolour, sharpen, or regenerate the frame. Read `references/alpha-matting.md` and run its one-time setup before the first Alpha Matting job. The default reduced matte crop restores original sure-foreground pixels and is the preferred speed mode; use `--alpha-max-matte-side 0` only for a failed edge case.

For translucent, gradient-lens, rimless, or semi-rimless eyewear:

1. Prefer the default `--fallback-mode cutout --edge-mode alpha`.
2. Inspect the guidance image, raw mask, trimap, and alpha mask before accepting the output.
3. Keep contrast guidance at the approved default; do not solve missing transparent edges by aggressively increasing contrast.
4. Increase `--alpha-background-erode` slightly when a thin transparent edge is still missing.
5. Reduce `--alpha-background-erode` when a broad gray fringe appears.
6. Use `--edge-mode binary` only for opaque products or when Alpha Matting is unavailable.
7. Preserve a small contact shadow only when it stays directly below the product.

Use `--fallback-mode background` only when contrast-guided cutout still cannot preserve a difficult transparent component.

For intentional close-up crops where the product reaches a canvas corner, add `--allow-edge-touch`. This only relaxes four-corner validation; it does not alter the matte or product pixels.

## Lens Reflection Repair

Lens inspection is mandatory for every eyewear image, including approved-asset and fast-reuse runs. If both lenses already look clean and natural, skip AI editing and preserve the original lens pixels exactly. Run a local AI repair only on a specifically identified studio reflection, glare, bright patch, scratch, or reflected object. Real temple arms, hinges, nose pads, and hardware visible through the tinted lenses are product structure, not reflections, and must remain unchanged. Read `references/lens-ai-repair.md` before editing.

The source image is the single source of truth for lens colour, tint density, transparency, and existing natural gradient. AI must heal only the identified unnatural reflection pixels. Do not re-grade, brighten, darken, neutralize, or rebuild the complete lens merely to make it look cleaner.

When the user provides an approved lens-treatment reference, use it only for blemish removal, tint smoothness, and gradient quality. The current source remains authoritative for lens colour, crop, frame geometry, logos, and every through-lens temple position.

Default to a small feathered defect mask that covers only the unnatural reflection, streak, glare spot, scratch, or blemish. A full-lens mask is forbidden unless the user explicitly requests a complete lens re-grade. If a local repair creates a boundary, retry with a slightly wider feathered defect mask while keeping the original surrounding tint; do not solve it by replacing the whole lens. Prepare a padded local crop with `scripts/lens_repair_workflow.py prepare`, send only `input.png` to built-in `$imagegen`, then run `composite`. Keep `mask.png` for the deterministic composite instead of using it as a visual reference. Never deliver the raw AI image.

When the AI proposal changes a real temple, hinge, logo, or lens rim, create a tight soft full-resolution protect mask for that structure and pass it to `composite --protect-mask`. White protect pixels always come from the approved source, while the remaining repair mask receives the AI lens cleanup.

For speed, repair both lenses in one crop when their gradients can be matched reliably; otherwise repair them independently. Use one medium-quality local edit first. Reinspect both lenses after every composite and retry only the failed region. No visible named defect means no repair mask and no AI edit, even when a reference image is available.

When AI repair is used, the first pass is not the completion gate. Reinspect both lenses at full-image scale and at least 200% close-up. If any thin arc, vertical line, doubled contour, cloudy patch, studio shape, glare, scratch, or uneven band remains, run a second isolated AI pass on only that residual defect. Deliver only after both lenses pass the second inspection with intact rims and through-lens structures.

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
- a remaining reflection on either lens after the other lens was repaired.
- any removed, shortened, blurred, displaced, or redrawn temple arm visible through either lens.
- any visible lens boundary line, polygon seam, cloudy band, white block, or abrupt tint transition.
- any local colour shift that makes the repaired pixels warmer, cooler, brighter, darker, or less transparent than the adjacent original lens.

Confirm the corner pixel is pure white unless the source intentionally touches that corner. Delete or leave temporary artifacts under `/tmp`; report and deliver only the final absolute output path.
