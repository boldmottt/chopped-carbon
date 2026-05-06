from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.segmentation import watershed

from .orientation import orientation_discontinuity


def _intensity_edges(gray: np.ndarray, sigma: float = 1.5) -> np.ndarray:
    f = cv2.GaussianBlur(gray.astype(np.float32) / 255.0, (0, 0), sigma)
    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)
    return np.sqrt(gx * gx + gy * gy)


def segment_chips(
    gray: np.ndarray,
    theta: np.ndarray,
    coherence: np.ndarray,
    boundary_sigma: float = 2.0,
    boundary_quantile: float = 0.7,
    min_chip_area: int = 60,
    intensity_weight: float = 0.6,
    orientation_weight: float = 0.6,
) -> tuple[np.ndarray, np.ndarray]:
    """Segment chips using intensity edges + orientation discontinuity.

    Returns (labels, boundary_mask).
    """
    disc = orientation_discontinuity(theta, sigma=boundary_sigma)
    intens = _intensity_edges(gray, sigma=boundary_sigma)

    if disc.max() > 0:
        disc_n = disc / (disc.max() + 1e-8)
    else:
        disc_n = disc
    if intens.max() > 0:
        intens_n = intens / (intens.max() + 1e-8)
    else:
        intens_n = intens

    combined = (orientation_weight * disc_n * (0.3 + 0.7 * coherence)
                + intensity_weight * intens_n)

    thr = float(np.quantile(combined, boundary_quantile))
    boundary_mask = combined > thr

    boundary_mask = cv2.morphologyEx(
        boundary_mask.astype(np.uint8),
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    ).astype(bool)

    interior = ~boundary_mask
    interior_d = ndi.distance_transform_edt(interior)
    peak_thr = max(2.5, float(np.quantile(interior_d[interior_d > 0], 0.85)) * 0.5)
    seeds_bin = (interior_d > peak_thr).astype(np.uint8)
    _, markers = cv2.connectedComponents(seeds_bin)

    labels = watershed(combined, markers=markers, mask=interior).astype(np.int32)

    if min_chip_area > 0:
        sizes = np.bincount(labels.ravel())
        small = np.where(sizes < min_chip_area)[0]
        for s in small:
            if s == 0:
                continue
            labels[labels == s] = 0

    return labels, boundary_mask


def chip_mean_intensity(gray: np.ndarray, labels: np.ndarray) -> dict[int, float]:
    means: dict[int, float] = {}
    ids = np.unique(labels)
    for i in ids:
        if i == 0:
            continue
        means[int(i)] = float(gray[labels == i].mean())
    return means


def chip_contours(labels: np.ndarray, simplify_eps: float = 1.5) -> dict[int, list[np.ndarray]]:
    """Extract chip outlines, simplified with Douglas-Peucker."""
    out: dict[int, list[np.ndarray]] = {}
    ids = np.unique(labels)
    for i in ids:
        if i == 0:
            continue
        m = (labels == i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        polys: list[np.ndarray] = []
        for c in contours:
            if len(c) < 4:
                continue
            approx = cv2.approxPolyDP(c, simplify_eps, True)
            if len(approx) < 3:
                continue
            polys.append(approx.reshape(-1, 2).astype(np.float32))
        if polys:
            out[int(i)] = polys
    return out
