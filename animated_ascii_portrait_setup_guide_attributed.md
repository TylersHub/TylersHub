# Animated ASCII Portrait for a GitHub Profile

> **Important:** This guide is an adaptation of an existing ASCII portrait workflow. It makes the setup easier to follow and the generator more configurable, but it does not claim ownership of the original script or technique.

A complete guide for turning a portrait photo into a self-typing ASCII SVG that works inside a GitHub profile README.

This setup follows the same core approach described in the referenced guide:

- remove the photo background,
- increase local contrast,
- darken midtones,
- convert the portrait into ASCII,
- embed the ASCII inside an SVG,
- animate each row with SMIL,
- embed a monospace font so the portrait keeps its shape,
- generate separate light and dark versions,
- commit the finished SVGs to your own profile repository.

No external image service is required after setup.

---


# Attribution and Authorship

This guide does **not** claim ownership of the original ASCII portrait idea or the original generator script.

The original generator appears to come from the Notion page:

**[ASCII Portrait README Guide](https://burly-handstand-0dc.notion.site/ASCII-Portrait-README-Guide-3a3e3f86338481f0b545ec8120bbf604)**

The original author of that script could not be reliably identified from the available page or repository history. Because the author is unknown, the script should not be presented as original code written by the person using this guide.

Andrii Drok later adapted and expanded the approach in his GitHub profile repository:

```text
https://github.com/andriidrok1/andriidrok1
```

His version added or documented improvements such as:

- a stronger darkening curve,
- tighter portrait defaults,
- cropping support,
- JetBrains Mono font embedding,
- GitHub profile integration,
- and clearer explanation of the SVG animation pipeline.

This Markdown guide and the configurable generator included here are intended to make the workflow easier to understand, set up, tune, and use. They should be described as an adaptation and usability-focused rewrite, not as an original invention.

A suitable credit notice is:

```markdown
## Credits

- Original ASCII portrait generator and SMIL typing concept:
  [ASCII Portrait README Guide](https://burly-handstand-0dc.notion.site/ASCII-Portrait-README-Guide-3a3e3f86338481f0b545ec8120bbf604). Original author unknown.
- Expanded implementation, darkening-curve improvements, font embedding,
  and profile integration:
  [Andrii Drok](https://github.com/andriidrok1/andriidrok1)
- This version reorganizes the setup, adds clearer documentation, and exposes
  more configuration options. It does not claim authorship of the original code.
- JetBrains Mono is distributed under the SIL Open Font License 1.1.
```

Because no confirmed open-source license was identified for the original Notion script, attribution alone should not be treated as permission to redistribute the original code verbatim. Anyone publishing a derivative should verify the applicable license or obtain permission from the relevant author.

---

# 1. What You Are Building

You will create two SVG files:

```text
assets/ascii-portrait-light.svg
assets/ascii-portrait-dark.svg
```

They will contain your portrait rendered using ASCII characters, an embedded JetBrains Mono subset, a row-by-row terminal-style reveal animation, a moving cursor block, and separate light/dark colors.

Your README will display the correct version automatically:

```html
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/ascii-portrait-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="./assets/ascii-portrait-light.svg" />
    <img src="./assets/ascii-portrait-light.svg" width="460" alt="Animated ASCII portrait" />
  </picture>
</p>
```

---

# 2. Requirements

You need Git, Python 3.10 or newer, VS Code or another editor, a GitHub profile repository, a high-resolution portrait, JetBrains Mono Regular, and PowerShell or another terminal.

Your GitHub profile repository must be named exactly the same as your GitHub username.

Example:

```text
GitHub username: TylersHub
Profile repository: <your-username>/<your-username>
```

---

# 3. Recommended Project Structure

```text
<your-username>/
├── README.md
├── assets/
│   ├── portrait-source.jpg
│   ├── ascii-portrait-light.svg
│   └── ascii-portrait-dark.svg
├── fonts/
│   ├── JetBrainsMono-Regular.ttf
│   ├── OFL.txt
│   └── ramp.woff2
├── scripts/
│   └── generate_portrait.py
└── .venv/
```

Add this to `.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
```

---

# 4. Clone and Prepare the Repository

```powershell
git clone https://github.com/<your-username>/<your-username>.git
cd <your-username>
New-Item -ItemType Directory -Force assets
New-Item -ItemType Directory -Force fonts
New-Item -ItemType Directory -Force scripts
```

Replace `TylersHub` with your own username if needed.

---

# 5. Create a Virtual Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

---

# 6. Install Dependencies

```powershell
pip install pillow numpy opencv-python-headless rembg onnxruntime fonttools brotli
```

| Package | Purpose |
|---|---|
| Pillow | Opens, converts, composites, and saves images |
| NumPy | Performs efficient math across image pixels |
| OpenCV Headless | Grayscale conversion, bilateral filtering, CLAHE, resizing, and sharpening |
| rembg | Removes the background using a pretrained model |
| onnxruntime | Runs the background-removal model |
| fonttools | Creates a small JetBrains Mono subset |
| brotli | Enables WOFF2 font compression |

The first `rembg` run may download a large model once and cache it.

---

# 7. Prepare the Portrait Photo

Use a portrait with side lighting at roughly 45 degrees, a plain background, a slight face angle, a tight crop, and high resolution. Your head should fill most of the frame.

Recommended crop:

```text
just above the hair
through
just below the chin
```

Recommended source resolution:

```text
1200 pixels or more
```

Avoid flat frontal lighting, distant photos, very small images, busy backgrounds, black clothing against a dark wall, and heavily compressed screenshots.

Save the portrait as:

```text
assets/portrait-source.jpg
```

Verify the filename:

```powershell
Get-ChildItem .\assets\
```

---

# 8. Download and Subset JetBrains Mono

Place these files in `fonts/`:

```text
fonts/JetBrainsMono-Regular.ttf
fonts/OFL.txt
```

Create the WOFF2 subset:

```powershell
pyftsubset "fonts/JetBrainsMono-Regular.ttf" --text=' .`:-=+*cs#%@' --flavor=woff2 --layout-features='' --no-hinting --output-file="fonts/ramp.woff2"
```

Do not use `-o`; use `--output-file=`.

Verify:

```powershell
Test-Path "fonts/ramp.woff2"
Get-Item "fonts/ramp.woff2"
```

---

# 9. Create the Generator Script

Create `scripts/generate_portrait.py` and paste the following:

```python
from __future__ import annotations

import argparse
import base64
import html
import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import remove

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "assets" / "portrait-source.jpg"
DEFAULT_FONT = REPO_ROOT / "fonts" / "ramp.woff2"
DEFAULT_LIGHT_OUTPUT = REPO_ROOT / "assets" / "ascii-portrait-light.svg"
DEFAULT_DARK_OUTPUT = REPO_ROOT / "assets" / "ascii-portrait-dark.svg"

COLS = 90
ASCII_RAMP = " .`:-=+*cs#%@"
CLAHE_CLIP_LIMIT = 3.0
CLAHE_TILE_SIZE = (8, 8)
DARKEN_EXPONENT = 1.7
FONT_SIZE = 12.9
CHAR_WIDTH = 7.74
LINE_HEIGHT = 15.5
ROW_DELAY = 0.09
ROW_DURATION = 0.45
PADDING_X = 18.0
PADDING_Y = 18.0
BILATERAL_DIAMETER = 7
BILATERAL_SIGMA_COLOR = 50
BILATERAL_SIGMA_SPACE = 50
SHARPEN_AMOUNT = 0.0
SHARPEN_RADIUS = 1.0

LIGHT_THEME = {
    "background": "#f6f8fa",
    "foreground": "#24292f",
    "cursor": "#0969da",
}

DARK_THEME = {
    "background": "#0d1117",
    "foreground": "#c9d1d9",
    "cursor": "#58a6ff",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate animated light and dark ASCII portrait SVGs."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--font", type=Path, default=DEFAULT_FONT)
    parser.add_argument("--light-output", type=Path, default=DEFAULT_LIGHT_OUTPUT)
    parser.add_argument("--dark-output", type=Path, default=DEFAULT_DARK_OUTPUT)
    parser.add_argument("--cols", type=int, default=COLS)
    parser.add_argument("--darken", type=float, default=DARKEN_EXPONENT)
    parser.add_argument("--clahe", type=float, default=CLAHE_CLIP_LIMIT)
    parser.add_argument("--bilateral-diameter", type=int, default=BILATERAL_DIAMETER)
    parser.add_argument("--bilateral-sigma-color", type=float, default=BILATERAL_SIGMA_COLOR)
    parser.add_argument("--bilateral-sigma-space", type=float, default=BILATERAL_SIGMA_SPACE)
    parser.add_argument("--sharpen", type=float, default=SHARPEN_AMOUNT)
    parser.add_argument("--sharpen-radius", type=float, default=SHARPEN_RADIUS)
    parser.add_argument("--row-delay", type=float, default=ROW_DELAY)
    parser.add_argument("--row-duration", type=float, default=ROW_DURATION)
    parser.add_argument("--font-size", type=float, default=FONT_SIZE)
    parser.add_argument("--char-width", type=float, default=CHAR_WIDTH)
    parser.add_argument("--line-height", type=float, default=LINE_HEIGHT)
    return parser.parse_args()


def remove_background(image_path: Path) -> Image.Image:
    source = Image.open(image_path).convert("RGBA")
    removed = remove(source)
    if isinstance(removed, bytes):
        removed = Image.open(io.BytesIO(removed)).convert("RGBA")
    removed = removed.convert("RGBA")
    white = Image.new("RGBA", removed.size, (255, 255, 255, 255))
    return Image.alpha_composite(white, removed).convert("RGB")


def process_grayscale(image: Image.Image, args: argparse.Namespace) -> np.ndarray:
    rgb = np.asarray(image, dtype=np.uint8)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.bilateralFilter(
        gray,
        d=args.bilateral_diameter,
        sigmaColor=args.bilateral_sigma_color,
        sigmaSpace=args.bilateral_sigma_space,
    )
    clahe = cv2.createCLAHE(
        clipLimit=args.clahe,
        tileGridSize=CLAHE_TILE_SIZE,
    )
    gray = clahe.apply(gray)

    if args.sharpen > 0:
        blurred = cv2.GaussianBlur(gray, (0, 0), args.sharpen_radius)
        gray = cv2.addWeighted(gray, 1.0 + args.sharpen, blurred, -args.sharpen, 0)

    normalized = gray.astype(np.float32) / 255.0
    darkened = np.power(normalized, args.darken)
    return np.clip(darkened * 255.0, 0, 255).astype(np.uint8)


def resize_for_ascii(gray: np.ndarray, cols: int) -> np.ndarray:
    h, w = gray.shape
    rows = max(1, int(cols * (h / w) * 0.48))
    return cv2.resize(gray, (cols, rows), interpolation=cv2.INTER_AREA)


def grayscale_to_ascii(gray: np.ndarray) -> list[str]:
    max_index = len(ASCII_RAMP) - 1
    inverse = 255.0 - gray.astype(np.float32)
    indices = np.rint(inverse / 255.0 * max_index).astype(np.int32)
    indices = np.clip(indices, 0, max_index)
    return ["".join(ASCII_RAMP[i] for i in row) for row in indices]


def fmt(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def build_svg(rows: list[str], font_b64: str, theme: dict[str, str], args: argparse.Namespace) -> str:
    art_width = max(len(row) for row in rows) * args.char_width
    art_height = len(rows) * args.line_height
    svg_width = art_width + PADDING_X * 2
    svg_height = art_height + PADDING_Y * 2

    defs: list[str] = []
    body: list[str] = []

    for i, row in enumerate(rows):
        start = i * args.row_delay
        end = start + args.row_duration
        y = PADDING_Y + i * args.line_height
        baseline = y + args.font_size
        clip_id = f"clip-{i}"
        escaped = html.escape(row, quote=False)

        defs.append(f'''<clipPath id="{clip_id}">
  <rect x="{fmt(PADDING_X)}" y="{fmt(y)}" width="0" height="{fmt(args.line_height)}">
    <animate attributeName="width" from="0" to="{fmt(art_width)}"
      dur="{fmt(args.row_duration)}s" begin="{fmt(start)}s" fill="freeze" />
  </rect>
</clipPath>''')

        body.append(f'''<text class="ascii" x="{fmt(PADDING_X)}" y="{fmt(baseline)}"
  clip-path="url(#{clip_id})" xml:space="preserve">{escaped}</text>
<rect class="cursor" x="{fmt(PADDING_X)}" y="{fmt(y)}"
  width="{fmt(args.char_width)}" height="{fmt(args.font_size)}" visibility="hidden">
  <set attributeName="visibility" to="visible" begin="{fmt(start)}s" />
  <animate attributeName="x" from="{fmt(PADDING_X)}" to="{fmt(PADDING_X + art_width)}"
    dur="{fmt(args.row_duration)}s" begin="{fmt(start)}s" fill="freeze" />
  <set attributeName="visibility" to="hidden" begin="{fmt(end)}s" />
</rect>''')

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(svg_width)}" height="{fmt(svg_height)}"
  viewBox="0 0 {fmt(svg_width)} {fmt(svg_height)}" role="img">
<style>
@font-face {{
  font-family: "PortraitMono";
  src: url("data:font/woff2;base64,{font_b64}") format("woff2");
}}
.ascii {{
  fill: {theme["foreground"]};
  font-family: "PortraitMono", monospace;
  font-size: {fmt(args.font_size)}px;
  white-space: pre;
}}
.cursor {{ fill: {theme["cursor"]}; }}
</style>
<rect width="100%" height="100%" rx="14" fill="{theme["background"]}" />
<defs>{''.join(defs)}</defs>
{''.join(body)}
</svg>'''


def main() -> None:
    args = parse_arguments()

    if not args.input.is_file():
        raise FileNotFoundError(f"Missing input image: {args.input}")
    if not args.font.is_file():
        raise FileNotFoundError(f"Missing font subset: {args.font}")

    subject = remove_background(args.input)
    gray = process_grayscale(subject, args)
    gray = resize_for_ascii(gray, args.cols)
    rows = grayscale_to_ascii(gray)
    font_b64 = base64.b64encode(args.font.read_bytes()).decode("ascii")

    args.light_output.parent.mkdir(parents=True, exist_ok=True)
    args.dark_output.parent.mkdir(parents=True, exist_ok=True)

    args.light_output.write_text(
        build_svg(rows, font_b64, LIGHT_THEME, args),
        encoding="utf-8",
    )
    args.dark_output.write_text(
        build_svg(rows, font_b64, DARK_THEME, args),
        encoding="utf-8",
    )

    print(f"Generated {args.light_output}")
    print(f"Generated {args.dark_output}")
    print(f"ASCII grid: {len(rows[0])} columns x {len(rows)} rows")


if __name__ == "__main__":
    main()
```

---

# 10. Generate and Preview

```powershell
python .\scripts\generate_portrait.py
Start-Process .\assets\ascii-portrait-dark.svg
Start-Process .\assets\ascii-portrait-light.svg
```

Refresh the browser to replay the animation.

---

# 11. Generator Flags

Display help:

```powershell
python .\scripts\generate_portrait.py --help
```

## File Flags

| Flag | Default | Purpose |
|---|---|---|
| `--input` | `assets/portrait-source.jpg` | Source portrait path |
| `--font` | `fonts/ramp.woff2` | Embedded WOFF2 subset |
| `--light-output` | `assets/ascii-portrait-light.svg` | Light SVG output |
| `--dark-output` | `assets/ascii-portrait-dark.svg` | Dark SVG output |

## Detail and Image Flags

| Flag | Default | Recommended Range | Effect |
|---|---:|---:|---|
| `--cols` | 90 | 88–110 | More columns preserve more detail |
| `--clahe` | 3.0 | 2.0–4.0 | Raises local contrast |
| `--darken` | 1.7 | 1.4–2.0 | Darkens midtones |
| `--bilateral-diameter` | 7 | 5–9 | Smoothing neighborhood size |
| `--bilateral-sigma-color` | 50 | 25–60 | Brightness mixing strength |
| `--bilateral-sigma-space` | 50 | 25–60 | Spatial smoothing reach |
| `--sharpen` | 0 | 0.15–0.45 | Adds edge contrast |
| `--sharpen-radius` | 1.0 | 0.6–1.5 | Width of sharpened edges |

## Animation Flags

| Flag | Default | Recommended Range | Effect |
|---|---:|---:|---|
| `--row-delay` | 0.09 | 0.05–0.12 | Delay between row starts |
| `--row-duration` | 0.45 | 0.25–0.65 | Horizontal wipe duration |

## Geometry Flags

| Flag | Default | Meaning |
|---|---:|---|
| `--font-size` | 12.9 | SVG font size |
| `--char-width` | 7.74 | Expected character advance |
| `--line-height` | 15.5 | Distance between rows |

Do not casually change `--char-width`; it is tied to JetBrains Mono's 0.600em advance width.

---

# 12. Useful Presets

## Default

```powershell
python .\scripts\generate_portrait.py
```

## More Eye Detail

```powershell
python .\scripts\generate_portrait.py `
  --cols 100 `
  --clahe 3.5 `
  --bilateral-diameter 5 `
  --bilateral-sigma-color 35 `
  --bilateral-sigma-space 35 `
  --sharpen 0.25 `
  --sharpen-radius 0.8
```

## Very Detailed

```powershell
python .\scripts\generate_portrait.py `
  --cols 110 `
  --clahe 3.6 `
  --darken 1.7 `
  --bilateral-diameter 5 `
  --bilateral-sigma-color 30 `
  --bilateral-sigma-space 30 `
  --sharpen 0.3 `
  --sharpen-radius 0.8
```

## Softer

```powershell
python .\scripts\generate_portrait.py `
  --cols 90 `
  --clahe 2.6 `
  --darken 1.6
```

## Faster Animation

```powershell
python .\scripts\generate_portrait.py --row-delay 0.05 --row-duration 0.25
```

## Slower Animation

```powershell
python .\scripts\generate_portrait.py --row-delay 0.11 --row-duration 0.6
```

---

# 13. README Integration

```html
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./assets/ascii-portrait-dark.svg" />
    <source media="(prefers-color-scheme: light)" srcset="./assets/ascii-portrait-light.svg" />
    <img src="./assets/ascii-portrait-light.svg" width="460" alt="Animated ASCII portrait" />
  </picture>
</p>
```

Generate at 100 columns while still displaying at 460 pixels to increase internal detail without making the portrait physically larger.

---

# 14. Commit the Result

```powershell
git add README.md assets scripts fonts .gitignore
git commit -m "feat: add animated ASCII portrait"
git push
```

---

# 15. Troubleshooting

## Eyes lack detail

```powershell
python .\scripts\generate_portrait.py `
  --cols 100 `
  --clahe 3.5 `
  --bilateral-diameter 5 `
  --bilateral-sigma-color 35 `
  --bilateral-sigma-space 35 `
  --sharpen 0.25 `
  --sharpen-radius 0.8
```

Also crop more tightly.

## Washed out

```powershell
python .\scripts\generate_portrait.py --darken 1.8
```

## Too dark

```powershell
python .\scripts\generate_portrait.py --darken 1.5
```

## Too noisy

```powershell
python .\scripts\generate_portrait.py --clahe 2.5 --sharpen 0.15
```

## Too narrow on Windows

Verify `ramp.woff2` exists and the generated SVG contains an embedded `@font-face`. A fallback font can change character width and distort the portrait.

## Animation appears blank in screenshots

Some full-page screenshot tools restart SMIL. Use a tall fixed viewport and wait for the animation to finish.

## Animation does not loop

That is intentional. `fill="freeze"` keeps the final image visible after the one-time reveal.

---

# 16. Low-Level Explanation

## Image Matrix

A grayscale image is a two-dimensional matrix of brightness values from 0 to 255. NumPy and OpenCV process these values directly.

## Background Removal

`rembg` predicts a foreground mask. Transparent background pixels are composited onto white. White maps to the leading space in the ASCII ramp, so the background becomes empty text.

## Grayscale

RGB color becomes one brightness value because ASCII density represents brightness rather than color.

## Bilateral Filter

A bilateral filter considers both pixel distance and brightness difference. It smooths skin and compression noise while preserving stronger boundaries such as eyes, brows, glasses, hairlines, and the jaw.

## CLAHE

CLAHE means Contrast Limited Adaptive Histogram Equalization. It improves contrast in small image tiles rather than applying one global adjustment. The contrast limit prevents local noise from being amplified too aggressively.

## Darkening Curve

The script normalizes brightness into 0–1 and applies:

```python
normalized ** 1.7
```

For values between zero and one, an exponent above one reduces midtone values, making them darker. This helps facial structure survive conversion into only 13 brightness levels.

## ASCII Ramp

```text
 .`:-=+*cs#%@
```

The ramp is ordered from visually light to dense. White maps to a space; black maps to `@`.

## Aspect Correction

```python
rows = int(cols * (height / width) * 0.48)
```

Monospace characters are taller than they are wide. The `0.48` factor prevents the portrait from becoming vertically stretched.

## Embedded Font

ASCII depends on fixed geometry. The SVG embeds a small JetBrains Mono WOFF2 subset as Base64 so every visitor uses the same 0.600em character advance rather than a system-dependent fallback.

## SVG

SVG can contain text, rectangles, clipping paths, embedded fonts, and animation. It scales cleanly because it is vector-based.

## SMIL

SMIL is SVG's built-in animation language. `<animate>` changes an attribute over time, and `<set>` changes an attribute at a specific moment.

## Reveal Mechanism

Every row already exists. A `clipPath` rectangle starts with width zero and expands across the row. Only the portion inside the rectangle is visible, creating a typing-like wipe.

## Cursor

A small rectangle moves with the reveal edge. A `<set>` hides it when the row completes.

## Staggering

```python
row_start = row_index * row_delay
```

With a 0.09-second delay, each consecutive row begins slightly later, producing the top-to-bottom printing effect.

## `fill="freeze"`

This keeps the final animated value instead of resetting. Rows remain visible after printing.

## Why GitHub Allows It

GitHub strips scripts and inline SVG from README Markdown, but it allows an external SVG referenced through `<img>` or `<picture>`. The animation therefore lives inside the SVG file itself.

---

# 17. Final Checklist

- [ ] Profile repository is named after the GitHub username.
- [ ] Virtual environment is active.
- [ ] Dependencies are installed.
- [ ] Portrait is high resolution and tightly cropped.
- [ ] `assets/portrait-source.jpg` exists.
- [ ] `fonts/JetBrainsMono-Regular.ttf` exists.
- [ ] `fonts/OFL.txt` exists.
- [ ] `fonts/ramp.woff2` exists.
- [ ] Generator runs successfully.
- [ ] Both SVGs are generated.
- [ ] Light and dark versions look correct.
- [ ] Animation finishes and stops.
- [ ] README uses the `<picture>` block.
- [ ] `.venv` is ignored.
- [ ] Final files are committed and pushed.

---

# 18. Regenerating Later

Regenerate whenever you change the source photo, processing settings, ASCII resolution, colors, animation timing, or font geometry:

```powershell
python .\scripts\generate_portrait.py
```

Then commit the SVGs:

```powershell
git add assets/ascii-portrait-light.svg assets/ascii-portrait-dark.svg
git commit -m "style: refine ASCII portrait"
git push
```

The portrait does not need a scheduled GitHub Actions workflow unless you intentionally want automatic regeneration.
