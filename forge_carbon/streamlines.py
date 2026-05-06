from __future__ import annotations

import numpy as np


def _bilinear_safe(field: np.ndarray, x: float, y: float) -> float:
    h, w = field.shape[:2]
    if x < 0.0 or y < 0.0 or x > w - 1 or y > h - 1:
        return 0.0
    x0 = int(x)
    y0 = int(y)
    x1 = x0 + 1 if x0 + 1 < w else x0
    y1 = y0 + 1 if y0 + 1 < h else y0
    fx = x - x0
    fy = y - y0
    a = field[y0, x0] * (1 - fx) + field[y0, x1] * fx
    b = field[y1, x0] * (1 - fx) + field[y1, x1] * fx
    return float(a * (1 - fy) + b * fy)


class _Grid:
    """Spatial hash: cell (cx,cy) holds list of (x,y) of streamline samples."""

    def __init__(self, w: int, h: int, cell: float):
        self.cell = cell
        self.gw = int(w / cell) + 2
        self.gh = int(h / cell) + 2
        self.cells: dict[int, list[tuple[float, float]]] = {}

    def _key(self, cx: int, cy: int) -> int:
        return cy * self.gw + cx

    def add(self, x: float, y: float) -> None:
        cx = int(x / self.cell)
        cy = int(y / self.cell)
        self.cells.setdefault(self._key(cx, cy), []).append((x, y))

    def has_within(self, x: float, y: float, r: float) -> bool:
        cx = int(x / self.cell)
        cy = int(y / self.cell)
        r2 = r * r
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                bucket = self.cells.get(self._key(cx + dx, cy + dy))
                if not bucket:
                    continue
                for px, py in bucket:
                    if (px - x) * (px - x) + (py - y) * (py - y) < r2:
                        return True
        return False


def _trace_one(
    seed: tuple[float, float],
    c2: np.ndarray,
    s2: np.ndarray,
    coh: np.ndarray,
    boundary_mask: np.ndarray | None,
    grid: _Grid,
    step: float,
    max_steps: int,
    coh_thresh: float,
    sep: float,
    angle_break: float,
) -> list[tuple[float, float]]:
    h, w = coh.shape
    forward: list[tuple[float, float]] = []
    backward: list[tuple[float, float]] = []
    cos_break = np.cos(angle_break)

    for direction in (1.0, -1.0):
        x, y = seed
        prev_vx = 0.0
        prev_vy = 0.0
        first = True
        out_list = forward if direction > 0 else backward
        for _ in range(max_steps):
            if x < 1.0 or y < 1.0 or x > w - 2 or y > h - 2:
                break
            if _bilinear_safe(coh, x, y) < coh_thresh:
                break
            if boundary_mask is not None:
                if boundary_mask[int(y), int(x)]:
                    break

            cv = _bilinear_safe(c2, x, y)
            sv = _bilinear_safe(s2, x, y)
            ang = 0.5 * np.arctan2(sv, cv)
            vx = float(np.cos(ang))
            vy = float(np.sin(ang))
            if first:
                vx *= direction
                vy *= direction
                first = False
            else:
                if vx * prev_vx + vy * prev_vy < 0.0:
                    vx = -vx
                    vy = -vy
                if vx * prev_vx + vy * prev_vy < cos_break:
                    break

            mx = x + 0.5 * step * vx
            my = y + 0.5 * step * vy
            cv2_ = _bilinear_safe(c2, mx, my)
            sv2_ = _bilinear_safe(s2, mx, my)
            ang2 = 0.5 * np.arctan2(sv2_, cv2_)
            vx2 = float(np.cos(ang2))
            vy2 = float(np.sin(ang2))
            if vx2 * vx + vy2 * vy < 0.0:
                vx2 = -vx2
                vy2 = -vy2

            xn = x + step * vx2
            yn = y + step * vy2

            if grid.has_within(xn, yn, sep):
                break

            out_list.append((xn, yn))
            x = xn
            y = yn
            prev_vx = vx2
            prev_vy = vy2

    return list(reversed(backward)) + [seed] + forward


def evenly_spaced_streamlines(
    theta: np.ndarray,
    coherence: np.ndarray,
    spacing: float = 4.0,
    step: float = 1.0,
    max_len: int = 200,
    min_len: int = 8,
    coh_thresh: float = 0.15,
    boundary_mask: np.ndarray | None = None,
    seed_jitter: float = 0.5,
    angle_break_deg: float = 35.0,
    rng: np.random.Generator | None = None,
) -> list[list[tuple[float, float]]]:
    rng = rng if rng is not None else np.random.default_rng(0)
    h, w = theta.shape
    c2 = np.cos(2.0 * theta).astype(np.float32)
    s2 = np.sin(2.0 * theta).astype(np.float32)

    grid = _Grid(w, h, cell=spacing)

    seeds_x = max(1, int(w / spacing))
    seeds_y = max(1, int(h / spacing))
    sx = np.linspace(spacing, w - spacing, seeds_x)
    sy = np.linspace(spacing, h - spacing, seeds_y)
    seeds = []
    for y in sy:
        for x in sx:
            seeds.append((float(x + rng.uniform(-1, 1) * seed_jitter * spacing),
                          float(y + rng.uniform(-1, 1) * seed_jitter * spacing)))
    rng.shuffle(seeds)

    streamlines: list[list[tuple[float, float]]] = []
    angle_break = np.deg2rad(angle_break_deg)

    for sxy in seeds:
        x, y = sxy
        if x < 1 or y < 1 or x > w - 2 or y > h - 2:
            continue
        if coherence[int(y), int(x)] < coh_thresh:
            continue
        if boundary_mask is not None and boundary_mask[int(y), int(x)]:
            continue
        if grid.has_within(x, y, spacing):
            continue

        line = _trace_one(
            sxy, c2, s2, coherence, boundary_mask,
            grid, step=step, max_steps=max_len,
            coh_thresh=coh_thresh, sep=spacing,
            angle_break=angle_break,
        )
        if len(line) >= min_len:
            for px, py in line:
                grid.add(px, py)
            streamlines.append(line)

    return streamlines


def simplify_polyline(points: list[tuple[float, float]], min_dist: float) -> list[tuple[float, float]]:
    if len(points) < 2:
        return points
    out = [points[0]]
    md2 = min_dist * min_dist
    for x, y in points[1:]:
        px, py = out[-1]
        if (x - px) ** 2 + (y - py) ** 2 >= md2:
            out.append((x, y))
    if out[-1] != points[-1]:
        out.append(points[-1])
    return out
