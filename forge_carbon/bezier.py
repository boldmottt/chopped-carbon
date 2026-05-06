from __future__ import annotations

import numpy as np


def smooth_polyline(points: np.ndarray, window: int = 5) -> np.ndarray:
    if len(points) < window:
        return points
    k = window // 2
    pad = np.pad(points, ((k, k), (0, 0)), mode="edge")
    kernel = np.ones(window) / window
    sx = np.convolve(pad[:, 0], kernel, mode="valid")
    sy = np.convolve(pad[:, 1], kernel, mode="valid")
    return np.column_stack([sx, sy]).astype(np.float32)


def polyline_to_cubic_bezier(points: np.ndarray, alpha: float = 0.5) -> list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """Catmull-Rom to cubic Bezier conversion. alpha in [0,1] is tension (0.5 = centripetal)."""
    n = len(points)
    if n < 2:
        return []
    if n == 2:
        p0, p3 = points[0], points[1]
        p1 = p0 + (p3 - p0) / 3.0
        p2 = p0 + 2.0 * (p3 - p0) / 3.0
        return [(p0, p1, p2, p3)]

    p = np.vstack([points[0], points, points[-1]]).astype(np.float32)
    segs = []
    for i in range(1, len(p) - 2):
        p0 = p[i - 1]
        p1 = p[i]
        p2 = p[i + 1]
        p3 = p[i + 2]
        c1 = p1 + (p2 - p0) * (alpha / 3.0)
        c2 = p2 - (p3 - p1) * (alpha / 3.0)
        segs.append((p1, c1, c2, p2))
    return segs


def bezier_path_d(segs: list[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]], precision: int = 2) -> str:
    if not segs:
        return ""
    fmt = f"{{:.{precision}f}}"
    parts: list[str] = []
    p0 = segs[0][0]
    parts.append("M " + fmt.format(p0[0]) + " " + fmt.format(p0[1]))
    for _, c1, c2, p3 in segs:
        parts.append(
            "C " + fmt.format(c1[0]) + " " + fmt.format(c1[1])
            + " " + fmt.format(c2[0]) + " " + fmt.format(c2[1])
            + " " + fmt.format(p3[0]) + " " + fmt.format(p3[1])
        )
    return " ".join(parts)


def contour_to_bezier_d(contour: np.ndarray, alpha: float = 0.5, precision: int = 2) -> str:
    if len(contour) < 3:
        return ""
    closed = np.vstack([contour, contour[:2]]).astype(np.float32)
    segs = polyline_to_cubic_bezier(closed, alpha=alpha)
    if not segs:
        return ""
    fmt = f"{{:.{precision}f}}"
    p0 = segs[0][0]
    parts = ["M " + fmt.format(p0[0]) + " " + fmt.format(p0[1])]
    for _, c1, c2, p3 in segs[:-1]:
        parts.append(
            "C " + fmt.format(c1[0]) + " " + fmt.format(c1[1])
            + " " + fmt.format(c2[0]) + " " + fmt.format(c2[1])
            + " " + fmt.format(p3[0]) + " " + fmt.format(p3[1])
        )
    parts.append("Z")
    return " ".join(parts)
