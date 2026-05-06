from __future__ import annotations

import cv2
import numpy as np


def structure_tensor_field(
    gray: np.ndarray,
    inner_sigma: float = 1.2,
    outer_sigma: float = 4.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute per-pixel orientation, coherence, and energy via structure tensor.

    Returns (theta, coherence, energy) where:
      - theta in [0, pi): direction along which intensity is most uniform (fiber direction)
      - coherence in [0, 1]: how anisotropic the local neighborhood is
      - energy: sum of eigenvalues (gradient magnitude squared, smoothed)
    """
    f = gray.astype(np.float32) / 255.0
    f = cv2.GaussianBlur(f, (0, 0), inner_sigma)

    gx = cv2.Sobel(f, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(f, cv2.CV_32F, 0, 1, ksize=3)

    jxx = cv2.GaussianBlur(gx * gx, (0, 0), outer_sigma)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), outer_sigma)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), outer_sigma)

    trace = jxx + jyy
    diff = jxx - jyy
    disc = np.sqrt(diff * diff + 4.0 * jxy * jxy + 1e-12)

    lam1 = 0.5 * (trace + disc)
    lam2 = 0.5 * (trace - disc)

    # eigenvector of larger eigenvalue points along strongest gradient;
    # fiber direction is perpendicular to that.
    grad_angle = 0.5 * np.arctan2(2.0 * jxy, diff + 1e-12)
    theta = grad_angle + np.pi / 2.0
    theta = np.mod(theta, np.pi)

    coherence = np.zeros_like(trace)
    mask = trace > 1e-8
    coherence[mask] = ((lam1[mask] - lam2[mask]) / (lam1[mask] + lam2[mask])) ** 2

    return theta.astype(np.float32), coherence.astype(np.float32), trace.astype(np.float32)


def double_angle_vector(theta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (cos2theta, sin2theta) which is continuous across the pi-wrap."""
    return np.cos(2.0 * theta).astype(np.float32), np.sin(2.0 * theta).astype(np.float32)


def orientation_discontinuity(theta: np.ndarray, sigma: float = 2.0) -> np.ndarray:
    """Boundary likelihood from local change in orientation, robust to pi-wrap."""
    c2, s2 = double_angle_vector(theta)
    c2s = cv2.GaussianBlur(c2, (0, 0), sigma)
    s2s = cv2.GaussianBlur(s2, (0, 0), sigma)
    cgx = cv2.Sobel(c2s, cv2.CV_32F, 1, 0, ksize=3)
    cgy = cv2.Sobel(c2s, cv2.CV_32F, 0, 1, ksize=3)
    sgx = cv2.Sobel(s2s, cv2.CV_32F, 1, 0, ksize=3)
    sgy = cv2.Sobel(s2s, cv2.CV_32F, 0, 1, ksize=3)
    return np.sqrt(cgx * cgx + cgy * cgy + sgx * sgx + sgy * sgy)
