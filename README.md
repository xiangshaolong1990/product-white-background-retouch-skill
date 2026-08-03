# Product White-Background Retouch Skill

Codex skill for eyewear and product white-background retouching. It uses a contrast-enhanced guidance image to recover the complete product silhouette, composites untouched source pixels, and supports tightly masked AI repair for unwanted lens reflections.

## Install

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/xiangshaolong1990/product-white-background-retouch-skill.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch"
```

Install Pillow for the Python used to run the scripts:

```bash
python3 -m pip install Pillow
```

## Use

Invoke `$product-white-background-retouch` in Codex, or run:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch/scripts/first_mode_retouch.py" \
  --input "/absolute/path/IMG_0001.JPG"
```

The fast path reuses an exact approved asset at `白底/IMG_0001-1.png`. When none exists, the script uses conservative background cleanup and requires visual review.

## Update

```bash
git -C "${CODEX_HOME:-$HOME/.codex}/skills/product-white-background-retouch" pull --ff-only
```

The conservative background mode works anywhere Pillow is available. The optional Vision cutout mode requires macOS, Swift, and Apple Command Line Tools.
