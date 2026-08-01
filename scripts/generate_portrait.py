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


# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_INPUT = REPO_ROOT / "assets" / "portrait-source.jpg"
DEFAULT_FONT = REPO_ROOT / "fonts" / "ramp.woff2"
DEFAULT_LIGHT_OUTPUT = REPO_ROOT / "assets" / "ascii-portrait-light.svg"
DEFAULT_DARK_OUTPUT = REPO_ROOT / "assets" / "ascii-portrait-dark.svg"


# ---------------------------------------------------------------------
# Portrait settings from the guide
# ---------------------------------------------------------------------

COLS = 90

ASCII_RAMP = " .`:-=+*cs#%@"

CLAHE_CLIP_LIMIT = 3.0
CLAHE_TILE_SIZE = (8, 8)

DARKEN_EXPONENT = 1.7

# Monospace character geometry used by the guide.
FONT_SIZE = 12.9
CHAR_WIDTH = 7.74
LINE_HEIGHT = 15.5

# Each row starts 0.09 seconds after the previous row.
ROW_DELAY = 0.09

# The guide does not prescribe an exact horizontal wipe duration.
# 0.45 seconds gives a visible terminal-printing effect.
ROW_DURATION = 0.45

PADDING_X = 18.0
PADDING_Y = 18.0

# Cursor dimensions.
CURSOR_WIDTH = CHAR_WIDTH
CURSOR_HEIGHT = FONT_SIZE

# Image-processing settings.
BILATERAL_DIAMETER = 7
BILATERAL_SIGMA_COLOR = 50
BILATERAL_SIGMA_SPACE = 50


# ---------------------------------------------------------------------
# Color themes
# ---------------------------------------------------------------------

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

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to the source portrait image.",
    )

    parser.add_argument(
        "--font",
        type=Path,
        default=DEFAULT_FONT,
        help="Path to the subset WOFF2 font.",
    )

    parser.add_argument(
        "--light-output",
        type=Path,
        default=DEFAULT_LIGHT_OUTPUT,
        help="Path for the light SVG.",
    )

    parser.add_argument(
        "--dark-output",
        type=Path,
        default=DEFAULT_DARK_OUTPUT,
        help="Path for the dark SVG.",
    )

    parser.add_argument(
        "--cols",
        type=int,
        default=COLS,
        help="Number of ASCII columns.",
    )

    parser.add_argument(
        "--darken",
        type=float,
        default=DARKEN_EXPONENT,
        help="Darkening curve exponent.",
    )

    parser.add_argument(
        "--clahe",
        type=float,
        default=CLAHE_CLIP_LIMIT,
        help="CLAHE clip limit.",
    )

    return parser.parse_args()


def validate_files(image_path: Path, font_path: Path) -> None:
    if not image_path.is_file():
        raise FileNotFoundError(
            f"Portrait image not found:\n{image_path}\n\n"
            "Place your photo at assets/portrait-source.jpg "
            "or pass --input with another path."
        )

    if not font_path.is_file():
        raise FileNotFoundError(
            f"Font subset not found:\n{font_path}\n\n"
            "Run Step 8 first to create fonts/ramp.woff2."
        )


def remove_background(image_path: Path) -> Image.Image:
    """
    Remove the image background using rembg and composite the subject
    over a solid white background.
    """

    source = Image.open(image_path).convert("RGBA")

    removed = remove(source)

    if isinstance(removed, bytes):
        removed = Image.open(io.BytesIO(removed)).convert("RGBA")
    elif not isinstance(removed, Image.Image):
        raise TypeError(
            "rembg returned an unsupported result type: "
            f"{type(removed).__name__}"
        )

    removed = removed.convert("RGBA")

    white_background = Image.new(
        "RGBA",
        removed.size,
        (255, 255, 255, 255),
    )

    composited = Image.alpha_composite(
        white_background,
        removed,
    )

    return composited.convert("RGB")


def process_grayscale(
    image: Image.Image,
    clahe_clip_limit: float,
    darken_exponent: float,
) -> np.ndarray:
    """
    Convert to grayscale, smooth with a bilateral filter, apply CLAHE,
    and apply the guide's power-based darkening curve.
    """

    rgb = np.asarray(image, dtype=np.uint8)

    grayscale = cv2.cvtColor(
        rgb,
        cv2.COLOR_RGB2GRAY,
    )

    smoothed = cv2.bilateralFilter(
        grayscale,
        d=BILATERAL_DIAMETER,
        sigmaColor=BILATERAL_SIGMA_COLOR,
        sigmaSpace=BILATERAL_SIGMA_SPACE,
    )

    clahe = cv2.createCLAHE(
        clipLimit=clahe_clip_limit,
        tileGridSize=CLAHE_TILE_SIZE,
    )

    contrasted = clahe.apply(smoothed)

    normalized = contrasted.astype(np.float32) / 255.0

    darkened = np.power(
        normalized,
        darken_exponent,
    )

    darkened = np.clip(
        darkened * 255.0,
        0,
        255,
    ).astype(np.uint8)

    return darkened


def resize_for_ascii(
    grayscale: np.ndarray,
    cols: int,
) -> np.ndarray:
    """
    Resize the image to the requested character width.

    The 0.48 correction compensates for monospace characters being
    roughly twice as tall as they are wide.
    """

    source_height, source_width = grayscale.shape

    if source_width <= 0 or source_height <= 0:
        raise ValueError("The processed image has invalid dimensions.")

    rows = max(
        1,
        int(cols * (source_height / source_width) * 0.48),
    )

    return cv2.resize(
        grayscale,
        (cols, rows),
        interpolation=cv2.INTER_AREA,
    )


def grayscale_to_ascii(
    grayscale: np.ndarray,
    ramp: str = ASCII_RAMP,
) -> list[str]:
    """
    Convert grayscale brightness values to ASCII characters.

    White maps to the leading space.
    Black maps to the final, densest character.
    """

    if not ramp:
        raise ValueError("ASCII ramp cannot be empty.")

    max_index = len(ramp) - 1

    inverse_brightness = 255.0 - grayscale.astype(np.float32)

    indices = np.rint(
        inverse_brightness / 255.0 * max_index
    ).astype(np.int32)

    indices = np.clip(
        indices,
        0,
        max_index,
    )

    rows: list[str] = []

    for row in indices:
        text_row = "".join(ramp[index] for index in row)

        # Preserve the fixed grid width. Do not rstrip the row.
        rows.append(text_row)

    return rows


def encode_font_as_base64(font_path: Path) -> str:
    return base64.b64encode(
        font_path.read_bytes()
    ).decode("ascii")


def format_number(value: float) -> str:
    """
    Format SVG numbers without unnecessary trailing zeros.
    """

    return f"{value:.3f}".rstrip("0").rstrip(".")


def build_svg(
    ascii_rows: list[str],
    font_base64: str,
    theme: dict[str, str],
    title: str,
) -> str:
    if not ascii_rows:
        raise ValueError("Cannot build an SVG from zero ASCII rows.")

    longest_row = max(len(row) for row in ascii_rows)

    art_width = longest_row * CHAR_WIDTH
    art_height = len(ascii_rows) * LINE_HEIGHT

    svg_width = art_width + (PADDING_X * 2)
    svg_height = art_height + (PADDING_Y * 2)

    definitions: list[str] = []
    content: list[str] = []

    for index, row in enumerate(ascii_rows):
        row_start = index * ROW_DELAY
        row_end = row_start + ROW_DURATION

        row_y = PADDING_Y + (index * LINE_HEIGHT)
        text_baseline = row_y + FONT_SIZE

        escaped_row = html.escape(
            row,
            quote=False,
        )

        clip_id = f"row-clip-{index}"

        definitions.append(
            f"""
    <clipPath id="{clip_id}">
      <rect
        x="{format_number(PADDING_X)}"
        y="{format_number(row_y)}"
        width="0"
        height="{format_number(LINE_HEIGHT)}"
      >
        <animate
          attributeName="width"
          from="0"
          to="{format_number(art_width)}"
          dur="{format_number(ROW_DURATION)}s"
          begin="{format_number(row_start)}s"
          fill="freeze"
        />
      </rect>
    </clipPath>""".rstrip()
        )

        cursor_start_x = PADDING_X
        cursor_end_x = PADDING_X + art_width

        content.append(
            f"""
  <text
    class="ascii"
    x="{format_number(PADDING_X)}"
    y="{format_number(text_baseline)}"
    clip-path="url(#{clip_id})"
    xml:space="preserve"
  >{escaped_row}</text>

  <rect
    class="cursor"
    x="{format_number(cursor_start_x)}"
    y="{format_number(row_y)}"
    width="{format_number(CURSOR_WIDTH)}"
    height="{format_number(CURSOR_HEIGHT)}"
    visibility="hidden"
  >
    <set
      attributeName="visibility"
      to="visible"
      begin="{format_number(row_start)}s"
    />

    <animate
      attributeName="x"
      from="{format_number(cursor_start_x)}"
      to="{format_number(cursor_end_x)}"
      dur="{format_number(ROW_DURATION)}s"
      begin="{format_number(row_start)}s"
      fill="freeze"
    />

    <set
      attributeName="visibility"
      to="hidden"
      begin="{format_number(row_end)}s"
    />
  </rect>""".rstrip()
        )

    definitions_text = "\n".join(definitions)
    content_text = "\n\n".join(content)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg
  xmlns="http://www.w3.org/2000/svg"
  width="{format_number(svg_width)}"
  height="{format_number(svg_height)}"
  viewBox="0 0 {format_number(svg_width)} {format_number(svg_height)}"
  role="img"
  aria-labelledby="portrait-title portrait-description"
>
  <title id="portrait-title">{html.escape(title)}</title>

  <desc id="portrait-description">
    An ASCII portrait that prints from top to bottom with a terminal cursor.
  </desc>

  <style>
    @font-face {{
      font-family: "PortraitMono";
      src: url("data:font/woff2;base64,{font_base64}") format("woff2");
      font-weight: 400;
      font-style: normal;
      font-display: block;
    }}

    .ascii {{
      fill: {theme["foreground"]};
      font-family: "PortraitMono", "JetBrains Mono", monospace;
      font-size: {format_number(FONT_SIZE)}px;
      font-weight: 400;
      white-space: pre;
    }}

    .cursor {{
      fill: {theme["cursor"]};
    }}
  </style>

  <rect
    width="100%"
    height="100%"
    rx="14"
    fill="{theme["background"]}"
  />

  <defs>
{definitions_text}
  </defs>

{content_text}
</svg>
"""


def save_svg(path: Path, svg: str) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        svg,
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    args = parse_arguments()

    image_path = args.input.resolve()
    font_path = args.font.resolve()
    light_output = args.light_output.resolve()
    dark_output = args.dark_output.resolve()

    validate_files(
        image_path,
        font_path,
    )

    if args.cols <= 0:
        raise ValueError("--cols must be greater than zero.")

    if args.darken <= 0:
        raise ValueError("--darken must be greater than zero.")

    if args.clahe <= 0:
        raise ValueError("--clahe must be greater than zero.")

    print(f"Loading portrait: {image_path}")

    subject = remove_background(image_path)

    print("Background removed.")

    processed = process_grayscale(
        subject,
        clahe_clip_limit=args.clahe,
        darken_exponent=args.darken,
    )

    print(
        "Applied bilateral filtering, CLAHE, "
        f"and darkening exponent {args.darken}."
    )

    resized = resize_for_ascii(
        processed,
        cols=args.cols,
    )

    ascii_rows = grayscale_to_ascii(resized)

    print(
        f"Created ASCII grid: "
        f"{len(ascii_rows[0])} columns × {len(ascii_rows)} rows."
    )

    font_base64 = encode_font_as_base64(font_path)

    light_svg = build_svg(
        ascii_rows=ascii_rows,
        font_base64=font_base64,
        theme=LIGHT_THEME,
        title="Animated ASCII portrait of Tyler in light mode",
    )

    dark_svg = build_svg(
        ascii_rows=ascii_rows,
        font_base64=font_base64,
        theme=DARK_THEME,
        title="Animated ASCII portrait of Tyler in dark mode",
    )

    save_svg(
        light_output,
        light_svg,
    )

    save_svg(
        dark_output,
        dark_svg,
    )

    print()
    print("Generated:")
    print(f"  {light_output}")
    print(f"  {dark_output}")
    print()
    print(
        "Open either SVG in a browser and refresh the page "
        "to replay the animation."
    )


if __name__ == "__main__":
    main()