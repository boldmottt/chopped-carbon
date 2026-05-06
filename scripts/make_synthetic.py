#!/usr/bin/env python3
"""Generate a synthetic forged-carbon scan for pipeline testing."""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def make_chip_mask(h: int, w: int, n: int, rng: np.random.Generator) -> tuple[np.ndarray, list[dict]]:
    label = np.zeros((h, w), dtype=np.int32)
    info = []
    cid = 1
    attempts = 0
    while cid <= n and attempts < n * 30:
        attempts += 1
        cx = rng.integers(0, w)
        cy = rng.integers(0, h)
        sx = rng.integers(40, 110)
        sy = rng.integers(20, 50)
        ang = rng.uniform(0, np.pi)
        verts = []
        base = np.array([
            [-sx / 2, -sy / 2],
            [sx / 2, -sy / 2],
            [sx / 2, sy / 2],
            [-sx / 2, sy / 2],
        ], dtype=np.float32)
        base += rng.uniform(-8, 8, base.shape).astype(np.float32)
        c, s = np.cos(ang), np.sin(ang)
        rot = np.array([[c, -s], [s, c]], dtype=np.float32)
        pts = (base @ rot.T) + np.array([cx, cy], dtype=np.float32)
        pts_i = pts.astype(np.int32).reshape(-1, 1, 2)
        cv2.fillPoly(label, [pts_i], cid)
        info.append({"id": cid, "angle": ang, "center": (cx, cy)})
        cid += 1
    return label, info


def render(h: int, w: int, label: np.ndarray, info: list[dict], rng: np.random.Generator) -> np.ndarray:
    img = np.zeros((h, w), dtype=np.float32)
    bg = rng.uniform(8, 18, (h, w)).astype(np.float32)
    img += bg
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)

    for chip in info:
        cid = chip["id"]
        ang = chip["angle"]
        mask = label == cid
        if not mask.any():
            continue
        base_lum = rng.uniform(40, 220)
        line_amp = rng.uniform(20, 70)
        freq = rng.uniform(0.6, 1.2)
        c, s = np.cos(ang), np.sin(ang)
        u = c * xx + s * yy
        modulation = np.sin(2.0 * np.pi * freq * u + rng.uniform(0, 2 * np.pi))
        chip_img = base_lum + line_amp * modulation
        img = np.where(mask, chip_img, img)

    img += rng.normal(0, 4.0, img.shape).astype(np.float32)
    return np.clip(img, 0, 255).astype(np.uint8)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("-o", "--output", type=Path, default=Path("samples/synthetic.png"))
    p.add_argument("--width", type=int, default=1200)
    p.add_argument("--height", type=int, default=900)
    p.add_argument("--chips", type=int, default=180)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    rng = np.random.default_rng(args.seed)
    label, info = make_chip_mask(args.height, args.width, args.chips, rng)
    img = render(args.height, args.width, label, info, rng)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), img)
    print(f"wrote {args.output} ({args.width}x{args.height}, {len(info)} chips)")


if __name__ == "__main__":
    main()
