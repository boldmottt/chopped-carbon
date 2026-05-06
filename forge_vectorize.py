#!/usr/bin/env python3
"""Forged carbon scan -> vector fiber lines.

Pipeline:
  1. Load image (grayscale, optional CLAHE).
  2. Structure tensor: orientation field theta(x,y) + coherence c(x,y).
  3. Optional chip segmentation by orientation discontinuity + watershed.
  4. Evenly-spaced streamlines along theta, stopping on chip boundaries.
  5. Smooth + Catmull-Rom -> cubic Bezier; write SVG.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from forge_carbon.orientation import structure_tensor_field
from forge_carbon.streamlines import evenly_spaced_streamlines
from forge_carbon.segmentation import (
    chip_contours,
    chip_mean_intensity,
    segment_chips,
)
from forge_carbon.svg_writer import chip_paths_from_segmentation, write_svg


def _resize_to_max(img: np.ndarray, max_dim: int) -> tuple[np.ndarray, float]:
    h, w = img.shape[:2]
    long_edge = max(h, w)
    if long_edge <= max_dim:
        return img, 1.0
    scale = max_dim / float(long_edge)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA), scale


def _sample_along_line(img: np.ndarray, line: list[tuple[float, float]]) -> float:
    h, w = img.shape[:2]
    vals = []
    for x, y in line[:: max(1, len(line) // 8)]:
        xi = int(np.clip(x, 0, w - 1))
        yi = int(np.clip(y, 0, h - 1))
        vals.append(float(img[yi, xi]))
    return float(np.mean(vals)) if vals else 0.0


def _line_chip_id(labels: np.ndarray, line: list[tuple[float, float]]) -> int:
    h, w = labels.shape
    counts: dict[int, int] = {}
    for x, y in line[:: max(1, len(line) // 6)]:
        xi = int(np.clip(x, 0, w - 1))
        yi = int(np.clip(y, 0, h - 1))
        cid = int(labels[yi, xi])
        if cid > 0:
            counts[cid] = counts.get(cid, 0) + 1
    if not counts:
        return 0
    return max(counts.items(), key=lambda kv: kv[1])[0]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path, help="input scan image (jpg/png/tif)")
    p.add_argument("-o", "--output", type=Path, default=Path("output/forged.svg"))
    p.add_argument("--max-dim", type=int, default=2000,
                   help="resize so longest edge <= this (0 to disable)")
    p.add_argument("--clahe", action="store_true", help="apply CLAHE for local contrast")
    p.add_argument("--inner-sigma", type=float, default=1.2)
    p.add_argument("--outer-sigma", type=float, default=4.0)
    p.add_argument("--spacing", type=float, default=4.0,
                   help="target spacing between adjacent fibers (px in resized image)")
    p.add_argument("--step", type=float, default=1.0, help="streamline integration step")
    p.add_argument("--max-len", type=int, default=200)
    p.add_argument("--simplify", type=float, default=1.5,
                   help="drop polyline points closer than this (px) before bezier fit")
    p.add_argument("--min-len", type=int, default=8)
    p.add_argument("--coh-thresh", type=float, default=0.12)
    p.add_argument("--stroke-width", type=float, default=0.7)
    p.add_argument("--fiber-lo", type=float, default=130.0,
                   help="fiber line min gray (darkest fibers map here)")
    p.add_argument("--fiber-hi", type=float, default=240.0,
                   help="fiber line max gray (brightest fibers map here)")
    p.add_argument("--no-chips", action="store_true",
                   help="skip chip segmentation/fills, fibers only")
    p.add_argument("--draw-chip-fills", action="store_true",
                   help="render chip fill polygons under fibers")
    p.add_argument("--bg", type=float, default=8.0,
                   help="background gray level 0..255")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    t0 = time.time()
    img = cv2.imread(str(args.input), cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"failed to load: {args.input}", file=sys.stderr)
        return 2
    if args.verbose:
        print(f"[load] {img.shape[1]}x{img.shape[0]} in {time.time()-t0:.2f}s")

    if args.max_dim > 0:
        img, scale = _resize_to_max(img, args.max_dim)
        if args.verbose:
            print(f"[resize] -> {img.shape[1]}x{img.shape[0]} (scale={scale:.3f})")

    if args.clahe:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
        img = clahe.apply(img)

    h, w = img.shape

    t = time.time()
    theta, coh, energy = structure_tensor_field(
        img, inner_sigma=args.inner_sigma, outer_sigma=args.outer_sigma,
    )
    if args.verbose:
        print(f"[struct] in {time.time()-t:.2f}s, mean coherence={coh.mean():.3f}")

    boundary = None
    chip_paths = None
    chip_intensities: dict[int, float] = {}
    labels = None
    if not args.no_chips:
        t = time.time()
        labels, boundary = segment_chips(img, theta, coh)
        chip_intensities = chip_mean_intensity(img, labels)
        if args.verbose:
            n_chips = len(chip_intensities)
            print(f"[segment] {n_chips} chips in {time.time()-t:.2f}s")

    t = time.time()
    rng = np.random.default_rng(args.seed)
    lines = evenly_spaced_streamlines(
        theta, coh,
        spacing=args.spacing, step=args.step,
        max_len=args.max_len, min_len=args.min_len,
        coh_thresh=args.coh_thresh,
        boundary_mask=boundary,
        rng=rng,
    )
    if args.verbose:
        print(f"[streamlines] {len(lines)} lines in {time.time()-t:.2f}s")

    intensities = []
    for line in lines:
        sampled = _sample_along_line(img, line)
        if labels is not None:
            cid = _line_chip_id(labels, line)
            chip_mean = chip_intensities.get(cid, sampled)
            base = max(sampled, chip_mean)
        else:
            base = sampled
        v = args.fiber_lo + (base / 255.0) * (args.fiber_hi - args.fiber_lo)
        intensities.append(float(np.clip(v, 0, 255)))

    if args.draw_chip_fills and labels is not None:
        contours = chip_contours(labels)
        chip_paths = chip_paths_from_segmentation(contours, chip_intensities)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_svg(
        str(args.output), w, h,
        streamlines=lines,
        stroke_intensity=intensities,
        chip_paths=chip_paths,
        background_intensity=args.bg,
        stroke_width=args.stroke_width,
        simplify_min_dist=args.simplify,
    )
    if args.verbose:
        print(f"[write] {args.output} ({args.output.stat().st_size/1024:.1f} KB) total {time.time()-t0:.2f}s")
    else:
        print(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
