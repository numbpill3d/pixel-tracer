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


def trace(input_path: Path, output_path: Path, width: int, colors: int,
          threshold: float, jitter: float, seed: int, underlay: bool,
          background: tuple[int, int, int] = (250, 248, 238),
          ink: tuple[int, int, int] = (35, 35, 35)) -> None:
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
    parser = argparse.ArgumentParser(description="Create a low-res, MS Paint-like traced drawing for GIMP.")
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
    parser.add_argument("--open-gimp", action="store_true", help="open the finished PNG in GIMP if available")
    args = parser.parse_args()
    papers = {"ivory": (250, 248, 238), "white": (255, 255, 255), "gray": (232, 232, 232)}
    inks = {"charcoal": (35, 35, 35), "navy": (22, 46, 74), "green": (25, 75, 45)}
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
