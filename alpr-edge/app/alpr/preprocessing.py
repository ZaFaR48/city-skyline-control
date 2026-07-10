from __future__ import annotations

import cv2
import numpy as np


def preprocessing_variants(image: np.ndarray, max_variants: int = 5) -> list[tuple[str, np.ndarray]]:
    variants: list[tuple[str, np.ndarray]] = [("original", image)]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    variants.append(("grayscale", gray))
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(gray)
    variants.append(("contrast_enhanced", contrast))
    threshold = cv2.adaptiveThreshold(contrast, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 9)
    variants.append(("adaptive_threshold", threshold))
    variants.append(("inverted_threshold", cv2.bitwise_not(threshold)))
    return variants[: max(1, max_variants)]


def blur_score(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def edge_density(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    edges = cv2.Canny(gray, 80, 180)
    return float(np.count_nonzero(edges) / max(1, edges.size))
