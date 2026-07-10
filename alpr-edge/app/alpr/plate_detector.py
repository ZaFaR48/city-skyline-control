from __future__ import annotations

import time

import cv2
import numpy as np

from app.alpr.models import BoundingBox, PlateCandidate
from app.alpr.perspective import crop_bbox, crop_rotated_rect
from app.alpr.preprocessing import blur_score, edge_density


class HybridPlateDetector:
    def __init__(
        self,
        min_aspect_ratio: float = 1.5,
        max_aspect_ratio: float = 7.5,
        min_width_pixels: int = 50,
        max_candidates: int = 5,
        confidence_threshold: float = 0.35,
    ) -> None:
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio
        self.min_width_pixels = min_width_pixels
        self.max_candidates = max_candidates
        self.confidence_threshold = confidence_threshold
        self.model_version = "opencv-hybrid"

    def detect(self, vehicle_crop: np.ndarray) -> list[PlateCandidate]:
        started = time.perf_counter()
        del started
        gray = cv2.cvtColor(vehicle_crop, cv2.COLOR_BGR2GRAY) if vehicle_crop.ndim == 3 else vehicle_crop
        enhanced = cv2.equalizeHist(gray)
        blackhat_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 5))
        blackhat = cv2.morphologyEx(enhanced, cv2.MORPH_BLACKHAT, blackhat_kernel)
        grad_x = cv2.Sobel(blackhat, cv2.CV_32F, 1, 0, ksize=-1)
        grad_x = np.absolute(grad_x)
        min_val, max_val = float(grad_x.min()), float(grad_x.max())
        if max_val - min_val > 0:
            grad_x = (255 * ((grad_x - min_val) / (max_val - min_val))).astype("uint8")
        grad_x = cv2.GaussianBlur(grad_x, (5, 5), 0)
        close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
        closed = cv2.morphologyEx(grad_x, cv2.MORPH_CLOSE, close_kernel)
        _, thresh = cv2.threshold(closed, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        thresh = cv2.erode(thresh, None, iterations=1)
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates: list[PlateCandidate] = []
        h, w = vehicle_crop.shape[:2]
        for contour in contours:
            rect = cv2.minAreaRect(contour)
            (cx, cy), (rw, rh), angle = rect
            if rw <= 0 or rh <= 0:
                continue
            width, height = max(rw, rh), min(rw, rh)
            aspect = width / max(1.0, height)
            if not (self.min_aspect_ratio <= aspect <= self.max_aspect_ratio):
                continue
            if width < self.min_width_pixels:
                continue
            bbox_x, bbox_y, bbox_w, bbox_h = cv2.boundingRect(contour)
            bbox = BoundingBox(bbox_x, bbox_y, bbox_w, bbox_h).clipped(w, h)
            crop = crop_bbox(vehicle_crop, bbox)
            if crop.size == 0:
                continue
            corrected = crop_rotated_rect(vehicle_crop, rect)
            rectangularity = float(cv2.contourArea(contour) / max(1.0, bbox_w * bbox_h))
            edges = edge_density(crop)
            contrast = float(np.std(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop) / 128.0)
            blur = blur_score(crop)
            confidence = min(1.0, 0.25 + rectangularity * 0.35 + min(edges * 3, 0.25) + min(contrast, 0.15))
            if confidence < self.confidence_threshold:
                continue
            candidates.append(
                PlateCandidate(
                    bbox=bbox,
                    confidence=confidence,
                    angle=float(angle),
                    crop=crop,
                    corrected_crop=corrected if corrected.size else crop,
                    source="opencv_morphology",
                    diagnostics={
                        "aspect_ratio": float(aspect),
                        "rectangularity": rectangularity,
                        "edge_density": edges,
                        "contrast": contrast,
                        "blur_score": blur,
                    },
                )
            )
        return sorted(candidates, key=lambda item: item.confidence, reverse=True)[: self.max_candidates]
