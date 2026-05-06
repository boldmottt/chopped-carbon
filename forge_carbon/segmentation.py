from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.segmentation import watershed

from .orientation import orientation_discontinuity


def segment_chips(
    gray: np.ndarray,
    theta: np.ndarray,
    coherence: np.ndarray,
    boundary_sigma: float = 2.0,
    boundary_quantile: float = 0.7,
    min_chip_area: int = 60,
) -> tuple[np.ndarray, np.ndarray]:
    """Segment carbon chips using orientation discontinuity + watershed.

    Returns (labels, boundary_mask).
      - labels: int array, 0 = background/edge, 1..N = chip ids
      - boundary_mask: bool, True where streamlines should not cross
    """
    disc = orientation_discontinuity(theta, sigma=boundary_sigma)
    disc = disc * (0.3 + 0.7 * coherence)

    thr = float(np.quantile(disc, boundary_quantile))
    boundary_mask = disc > thr

    boundary_mask = cv2.morphologyEx(
        boundary_mask.astype(np.uint8),
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    ).astype(bool)

    interior = ~boundary_mask
    interior_d = ndi.distance_transform_edt(interior)
    peak_thr = max(2.5, float(np.quantile(interior_d[interior_d > 0], 0.85)) * 0.5)
    seeds_bin = (interior_d > peak_thr).astype(np.uint8)
    num, markers = cv2.connectedComponents(seeds_bin)

    labels = watershed(disc, markers=markers, mask=interior).astype(np.int32)

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


def chip_contours(labels: np.ndarray) -> dict[int, list[np.ndarray]]:
    out: dict[int, list[np.ndarray]] = {}
    ids = np.unique(labels)
    for i in ids:
        if i == 0:
            continue
        m = (labels == i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_TC89_KCOS)
        out[int(i)] = [c.reshape(-1, 2).astype(np.float32) for c in contours if len(c) >= 4]
    return out
