# Product White-Background Retouch Skill

Codex skill for eyewear and product white-background retouching. It uses a contrast-enhanced coarse mask plus trimap-based Alpha Matting to preserve translucent frame edges and keeps untouched source pixels in the product core. Lens inspection is mandatory, but AI repair is used only for a visible identified defect; clean natural lenses retain their original pixels.

## Install

Fresh install:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/xiangshaolong1990/product-white-background-retouch-skill.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch"
python3 -m pip install Pillow
/usr/bin/python3 "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch/scripts/setup_alpha_matting.py"
```

Replace an older installation with the latest repository version:

```bash
rm -rf "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch" && \
git clone https://github.com/xiangshaolong1990/product-white-background-retouch-skill.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch" && \
python3 -m pip install Pillow && \
/usr/bin/python3 "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch/scripts/setup_alpha_matting.py"
```

## Use

Invoke `$product-white-background-retouch` in Codex, or run:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch/scripts/first_mode_retouch.py" \
  --input "/absolute/path/IMG_0001.JPG"
```

The final-only wrapper keeps intermediate masks and crops in a temporary directory:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch/scripts/final_white_background_retouch.py" \
  --input "/absolute/path/IMG_0001.JPG"
```

The fast path reuses an exact approved asset at `白底/IMG_0001-1.png`. When none exists, the script uses contrast-guided segmentation and a reduced tight-crop Alpha Matting solve, restores original sure-foreground pixels, and writes only `IMG_0001修.png`.

For a deliberate close-up crop that touches a canvas corner, add `--allow-edge-touch` so validation does not mistake the product itself for background contamination.

## Update

```bash
git -C "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch" pull --ff-only
```

The conservative background mode works anywhere Pillow is available. Vision cutout requires macOS, Swift, and Apple Command Line Tools. Alpha Matting additionally uses the cached PyMatting runtime and falls back to the binary mask when that runtime is unavailable.
