# Alpha Matting for Translucent Frames

Binary subject masks can erase pale or semi-transparent frame pixels because every pixel must be classified as either foreground or background. Use trimap-based alpha matting for translucent eyewear edges.

## Method

1. Generate a coarse soft subject mask with macOS Vision.
2. Build a trimap with sure foreground, sure background, and an unknown edge band.
3. Estimate the alpha channel and foreground colour only inside a tight product crop.
4. Preserve untouched source pixels in the sure-foreground core.
5. Composite the estimated translucent edge onto pure white.

The implementation follows the same high-level trimap construction used by rembg's optional alpha-matting post-process and uses PyMatting's closed-form alpha estimation plus multi-level foreground estimation.

## One-Time Setup

```bash
SKILL_ROOT="${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch"
/usr/bin/python3 "$SKILL_ROOT/scripts/setup_alpha_matting.py"
```

The runtime is installed under:

```text
~/.cache/codex-product-white-background-retouch/alpha-matting-venv
```

If the runtime is unavailable, the retouch script falls back to the legacy binary edge mask unless `--alpha-fallback error` is selected.

## Sources

- PyMatting: https://github.com/pymatting/pymatting
- rembg alpha matting implementation: https://github.com/danielgatis/rembg/blob/main/rembg/bg.py
- ViTMatte reference implementation: https://github.com/hustvl/ViTMatte
