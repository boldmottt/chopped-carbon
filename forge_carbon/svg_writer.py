from __future__ import annotations

from typing import Iterable
import numpy as np

from .bezier import (
    bezier_path_d,
    contour_to_bezier_d,
    polyline_to_cubic_bezier,
    smooth_polyline,
)
from .streamlines import simplify_polyline


def _gray_hex(v: float) -> str:
    g = int(max(0, min(255, round(v))))
    return f"#{g:02x}{g:02x}{g:02x}"


def write_svg(
    path: str,
    width: int,
    height: int,
    streamlines: Iterable[list[tuple[float, float]]],
    stroke_intensity: Iterable[float],
    chip_paths: list[tuple[str, float]] | None = None,
    background_intensity: float = 8.0,
    stroke_width: float = 0.6,
    smooth_window: int = 5,
    bezier_alpha: float = 0.5,
    precision: int = 1,
    simplify_min_dist: float = 1.5,
) -> None:
    bg = _gray_hex(background_intensity)
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" shape-rendering="geometricPrecision">',
        f'  <rect width="100%" height="100%" fill="{bg}"/>',
    ]

    if chip_paths:
        out.append('  <g id="chips">')
        for d, intensity in chip_paths:
            if not d:
                continue
            fill = _gray_hex(intensity)
            out.append(f'    <path d="{d}" fill="{fill}" stroke="none"/>')
        out.append('  </g>')

    out.append('  <g id="fibers" fill="none" stroke-linecap="round">')
    streamlines = list(streamlines)
    intensities = list(stroke_intensity)
    for line, inten in zip(streamlines, intensities):
        if len(line) < 2:
            continue
        line = simplify_polyline(line, min_dist=simplify_min_dist)
        if len(line) < 2:
            continue
        arr = np.asarray(line, dtype=np.float32)
        arr = smooth_polyline(arr, window=smooth_window)
        segs = polyline_to_cubic_bezier(arr, alpha=bezier_alpha)
        d = bezier_path_d(segs, precision=precision)
        if not d:
            continue
        col = _gray_hex(inten)
        out.append(f'    <path d="{d}" stroke="{col}" stroke-width="{stroke_width:.2f}"/>')
    out.append('  </g>')
    out.append('</svg>')

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def chip_paths_from_segmentation(
    contours_per_chip: dict[int, list[np.ndarray]],
    intensities: dict[int, float],
    smooth_window: int = 3,
    bezier_alpha: float = 0.5,
    precision: int = 2,
) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for cid, contours in contours_per_chip.items():
        for c in contours:
            if len(c) < 4:
                continue
            sm = smooth_polyline(c, window=smooth_window)
            d = contour_to_bezier_d(sm, alpha=bezier_alpha, precision=precision)
            if d:
                out.append((d, intensities.get(cid, 60.0)))
    return out
