from __future__ import annotations

import cv2
import numpy as np

from app.alpr.models import BoundingBox


def order_points(points: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    rect[0] = points[np.argmin(sums)]
    rect[2] = points[np.argmax(sums)]
    diff = np.diff(points, axis=1)
    rect[1] = points[np.argmin(diff)]
    rect[3] = points[np.argmax(diff)]
    return rect


def four_point_transform(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    rect = order_points(points.astype("float32"))
    tl, tr, br, bl = rect
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = max(1, int(max(width_a, width_b)))
    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = max(1, int(max(height_a, height_b)))
    destination = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, destination)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def crop_rotated_rect(image: np.ndarray, rect: tuple) -> np.ndarray:
    box = cv2.boxPoints(rect)
    return four_point_transform(image, box)


def crop_bbox(image: np.ndarray, bbox: BoundingBox) -> np.ndarray:
    h, w = image.shape[:2]
    clipped = bbox.clipped(w, h)
    return image[clipped.y : clipped.y2, clipped.x : clipped.x2].copy()
