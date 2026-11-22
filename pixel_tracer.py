#!/usr/bin/env python3
"""Human-ish, low-resolution image tracer for GIMP.

Creates a deliberately pixelated drawing from an input image.  The drawing is
made at a small working resolution, with ordered, slightly imperfect strokes,
then enlarged with nearest-neighbour scaling so it keeps an MS Paint feel.
"""

from __future__ import annotations

import argparse
import random
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps


def edge_map(gray: np.ndarray) -> np.ndarray:
    """Cheap Sobel-like edge strength using only numpy."""
    gx = np.zeros_like(gray, dtype=float)
    gy = np.zeros_like(gray, dtype=float)
    gx[:, 1:-1] = gray[:, 2:] - gray[:, :-2]
    gy[1:-1, :] = gray[2:, :] - gray[:-2, :]
    strength = np.hypot(gx, gy)
    strength /= max(float(strength.max()), 1.0)
    return strength


def palette_image(img: Image.Image, colors: int) -> Image.Image:
    return img.convert("RGB").quantize(colors=max(2, colors), method=Image.Quantize.MEDIANCUT).convert("RGB")


def _bayer(width: int, height: int) -> np.ndarray:
    """Tile a 4x4 ordered-dither matrix across the working canvas."""
    matrix = np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]], dtype=float)
    return np.tile(matrix, (height // 4 + 1, width // 4 + 1))[:height, :width] / 16.0 - 0.5


def iter_line_strokes(input_path: Path, width: int, colors: int, threshold: float,
                      jitter: float, seed: int):
    """Yield ordered, imperfect contour strokes for the live drawing preview."""
    rng = random.Random(seed)
    source = Image.open(input_path).convert("RGB")
    height = max(16, round(width * source.height / source.width))
    small = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS)
    small = palette_image(small, colors)
    arr = np.asarray(small).astype(float) / 255.0
    gray = arr @ np.array([0.299, 0.587, 0.114])
    edges = edge_map(gray)
    h, w = edges.shape
    for y in range(1, h - 1):
        xs = np.flatnonzero(edges[y] >= threshold)
        if not len(xs):
            continue
        runs = []
        start = prev = int(xs[0])
        for x in xs[1:]:
            x = int(x)
            if x - prev > 2:
                runs.append((start, prev))
                start = x
            prev = x
        runs.append((start, prev))
        if y % 2:
            runs.reverse()
        for left, right in runs:
            if right - left < 1:
                continue
            step = max(1, (right - left) // 5)
            seq = list(range(left, right + 1, step))
            if y % 2:
                seq.reverse()
            points = [(x + rng.uniform(-jitter, jitter), y + rng.uniform(-jitter, jitter)) for x in seq]
            if len(points) > 1:
                yield points


def poster_trace(input_path: Path, output_path: Path, width: int, colors: int,
                 threshold: float, jitter: float, seed: int, underlay: bool,
                 background: tuple[int, int, int], ink: tuple[int, int, int],
                 chroma: int = 1, grain: float = 0.08,
                 caption: str = "") -> None:
    """Make a distressed pixel-print poster while preserving the source image."""
    rng = random.Random(seed)
    source = Image.open(input_path).convert("RGB")
    height = max(16, round(width * source.height / source.width))
    small = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS)
    small = palette_image(small, colors)
    arr = np.asarray(small).astype(float) / 255.0
    gray = arr @ np.array([0.299, 0.587, 0.114])
    edges = edge_map(gray)
    dither = _bayer(width, height)

    # Ordered dither plus deterministic grain creates the photocopied/screened texture.
    noise = np.array([[rng.uniform(-grain, grain) for _ in range(width)] for _ in range(height)])
    textured = np.clip(arr + (dither + noise)[..., None] * 0.10, 0, 1)
    art = Image.fromarray(np.uint8(textured * 255), "RGB")

    # Make the darkest edge pixels ink-black and keep the rest of the restricted palette.
    line_alpha = np.clip((edges - threshold) / max(0.01, 1.0 - threshold), 0, 1)
    line_alpha = Image.fromarray(np.uint8(line_alpha * 255), "L")
    ink_layer = Image.new("RGB", (width, height), ink)
    art = Image.composite(ink_layer, art, line_alpha.point(lambda p: int(min(255, p * 1.35))))

    if underlay:
        art = Image.blend(art, small, 0.18)

    # Offset color channels like a cheap misregistered print, but keep the black linework stable.
    if chroma:
        rgb = [np.asarray(art)[:, :, channel] for channel in range(3)]
        shifted = []
        for channel, offset in enumerate((-chroma, 0, chroma)):
            shifted.append(np.roll(rgb[channel], offset, axis=1))
        art = Image.fromarray(np.stack(shifted, axis=2).astype(np.uint8), "RGB")

    # Reapply a few hard ink pixels after channel shifting.
    draw = ImageDraw.Draw(art)
    for y, x in zip(*np.where(edges > min(0.98, threshold + 0.30))):
        if rng.random() < 0.22:
            draw.point((int(x), int(y)), fill=ink)

    if caption:
        band_y = max(0, height - max(18, height // 8))
        draw.rectangle((0, band_y, width, height), fill=(0, 0, 0))
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSansMono.ttf", max(6, width // 34))
        except OSError:
            font = None
        draw.text((max(3, width // 18), band_y + max(2, height // 42)), caption, fill=(235, 235, 220), font=font)

    scale = max(1, round(960 / max(width, 1)))
    result = art.resize((width * scale, height * scale), Image.Resampling.NEAREST)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)


def paint_trace(input_path: Path, output_path: Path, width: int, colors: int,
                threshold: float, seed: int, background: tuple[int, int, int],
                ink: tuple[int, int, int], underlay: bool = False) -> None:
    """Create a flat-color, one-working-pixel-line MS Paint-style drawing."""
    source = Image.open(input_path).convert("RGB")
    height = max(16, round(width * source.height / source.width))
    small = ImageOps.fit(source, (width, height), method=Image.Resampling.LANCZOS)
    small = palette_image(small, max(4, colors))
    arr = np.asarray(small).astype(float) / 255.0
    gray = arr @ np.array([0.299, 0.587, 0.114])
    edges = edge_map(gray)

    # Hard threshold: exactly one crisp working pixel of ink, with no soft halo.
    mask = Image.fromarray(np.uint8((edges >= threshold) * 255), "L")
    line_layer = Image.new("RGB", small.size, ink)
    art = Image.composite(line_layer, small, mask)
    if underlay:
        art = Image.blend(art, small, 0.12)

    # Keep the paper/background option meaningful for near-white source pixels.
    pixels = np.asarray(art).copy()
    source_pixels = np.asarray(small)
    near_white = np.all(source_pixels > 245, axis=2)
    pixels[near_white & (edges < threshold)] = background
    art = Image.fromarray(pixels.astype(np.uint8), "RGB")

    scale = max(1, round(960 / max(width, 1)))
    result = art.resize((width * scale, height * scale), Image.Resampling.NEAREST)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)


def trace(input_path: Path, output_path: Path, width: int, colors: int,
          threshold: float, jitter: float, seed: int, underlay: bool,
          background: tuple[int, int, int] = (250, 248, 238),
          ink: tuple[int, int, int] = (35, 35, 35), style: str = "trace",
          caption: str = "", chroma: int = 1, grain: float = 0.08,
          paper: str | None = None) -> None:
    papers = {"ivory": (250, 248, 238), "white": (255, 255, 255), "gray": (232, 232, 232)}
    inks = {"charcoal": (35, 35, 35), "navy": (22, 46, 74), "green": (25, 75, 45)}
    if paper is not None:
        background = papers[paper]
    if isinstance(ink, str):
        ink = inks[ink]
    if style == "paint":
        paint_trace(input_path, output_path, width, colors, threshold, seed,
                    background, ink, underlay)
        return
    if style == "poster":
        poster_trace(input_path, output_path, width, colors, threshold, jitter, seed,
                     underlay, background, ink, chroma=chroma, grain=grain, caption=caption)
        return
    rng = random.Random(seed)
    source = Image.open(input_path).convert("RGB")
    ratio = source.height / source.width
    height = max(8, round(width * ratio))
    small = ImageOps.contain(source, (width, height))
    canvas_size = small.size
    small = palette_image(small, colors)
    arr = np.asarray(small).astype(float) / 255.0
    gray = arr @ np.array([0.299, 0.587, 0.114])
    edges = edge_map(gray)

    # A warm, flat background and a nearly-black ink mimic early Paint output.
    base = Image.new("RGB", canvas_size, background)
    draw = ImageDraw.Draw(base)

    # Walk rows in alternating directions so the result feels drawn rather than
    # stamped.  Edge runs become short, imperfect polyline strokes.
    h, w = edges.shape
    for y in range(1, h - 1):
        xs = np.flatnonzero(edges[y] >= threshold)
        if not len(xs):
            continue
        runs = []
        start = prev = int(xs[0])
        for x in xs[1:]:
            x = int(x)
            if x - prev > 2:
                runs.append((start, prev))
                start = x
            prev = x
        runs.append((start, prev))
        if y % 2:
            runs.reverse()
        for left, right in runs:
            if right - left < 1:
                continue
            points = []
            step = max(1, (right - left) // 5)
            seq = range(left, right + 1, step)
            if y % 2:
                seq = reversed(list(seq))
            for x in seq:
                dx = rng.uniform(-jitter, jitter)
                dy = rng.uniform(-jitter, jitter)
                points.append((x + dx, y + dy))
            if len(points) > 1:
                draw.line(points, fill=ink, width=1, joint="curve")

    # A few sparse pixel accents preserve strong dark details lost by thresholding.
    for y, x in zip(*np.where(edges > min(0.98, threshold + 0.30))):
        if rng.random() < 0.18:
            draw.point((int(x), int(y)), fill=ink)

    if underlay:
        faded = small.convert("RGB").copy()
        faded = Image.blend(base, faded, 0.18)
        base = faded

    scale = max(1, round(640 / max(width, 1)))
    result = base.resize((canvas_size[0] * scale, canvas_size[1] * scale), Image.Resampling.NEAREST)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a low-res, distressed MS Paint / photocopy-style drawing for GIMP.")
    parser.add_argument("input", type=Path, help="source image")
    parser.add_argument("-o", "--output", type=Path, default=Path("pixel-trace.png"))
    parser.add_argument("--width", type=int, default=160, help="working pixel width before nearest-neighbour enlargement")
    parser.add_argument("--colors", type=int, default=12)
    parser.add_argument("--threshold", type=float, default=0.19)
    parser.add_argument("--jitter", type=float, default=0.55)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--underlay", action="store_true", help="faintly retain the source beneath the trace")
    parser.add_argument("--paper", choices=("ivory", "white", "gray"), default="ivory")
    parser.add_argument("--ink", choices=("charcoal", "navy", "green"), default="charcoal")
    parser.add_argument("--style", choices=("paint", "poster", "trace"), default="paint",
                        help="paint makes flat limited-color MS Paint art; poster adds print texture; trace makes line art")
    parser.add_argument("--chroma", type=int, default=1, help="horizontal RGB misregistration in working pixels")
    parser.add_argument("--grain", type=float, default=0.08, help="screen/photocopy grain amount")
    parser.add_argument("--caption", default="", help="optional caption in a black bottom bar")
    parser.add_argument("--open-gimp", action="store_true", help="open the finished PNG in GIMP if available")
    args = parser.parse_args()
    papers = {"ivory": (250, 248, 238), "white": (255, 255, 255), "gray": (232, 232, 232)}
    inks = {"charcoal": (35, 35, 35), "navy": (22, 46, 74), "green": (25, 75, 45)}
    if args.style == "paint":
        paint_trace(args.input, args.output, args.width, args.colors, args.threshold, args.seed,
                    papers[args.paper], inks[args.ink], args.underlay)
    elif args.style == "poster":
        poster_trace(args.input, args.output, args.width, args.colors, args.threshold, args.jitter,
                     args.seed, args.underlay, papers[args.paper], inks[args.ink],
                     args.chroma, args.grain, args.caption)
    else:
        trace(args.input, args.output, args.width, args.colors, args.threshold, args.jitter,
              args.seed, args.underlay, papers[args.paper], inks[args.ink])
    print(f"Wrote {args.output}")
    if args.open_gimp:
        try:
            subprocess.Popen(["gimp", str(args.output)])
        except FileNotFoundError:
            print("GIMP was not found; open the PNG manually in GIMP.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
