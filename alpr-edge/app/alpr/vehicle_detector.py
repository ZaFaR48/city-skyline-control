from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

from app.alpr.models import BoundingBox, VehicleDetection
from app.models_runtime.checksums import verify_sha256


COCO_VEHICLE_CLASSES = {
    3: "car",
    4: "motorcycle",
    6: "bus",
    8: "truck",
}


class VehicleDetectorError(RuntimeError):
    pass


class ONNXVehicleDetector:
    def __init__(
        self,
        model_path: Path | None,
        confidence_threshold: float = 0.4,
        enabled_classes: tuple[str, ...] = ("car", "bus", "truck", "motorcycle"),
        input_size: int | None = None,
        expected_sha256: str | None = None,
    ) -> None:
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.enabled_classes = set(enabled_classes)
        self.input_size = input_size
        self.expected_sha256 = expected_sha256
        self.session = None
        self.input_name: str | None = None
        self.model_version = "unloaded"

    @property
    def ready(self) -> bool:
        return self.session is not None

    def load(self) -> None:
        if self.model_path is None:
            raise VehicleDetectorError("VEHICLE_DETECTOR_MODEL_PATH is not configured")
        if not self.model_path.exists():
            raise VehicleDetectorError(f"Vehicle detector model missing: {self.model_path}")
        if self.expected_sha256 and not verify_sha256(self.model_path, self.expected_sha256):
            raise VehicleDetectorError("Vehicle detector SHA256 mismatch")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise VehicleDetectorError("onnxruntime is not installed") from exc
        self.session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.model_version = self.model_path.name

    def detect(self, frame: np.ndarray) -> list[VehicleDetection]:
        if self.session is None or self.input_name is None:
            self.load()
        assert self.session is not None and self.input_name is not None
        h, w = frame.shape[:2]
        input_tensor = self._preprocess(frame)
        started = time.perf_counter()
        outputs = self.session.run(None, {self.input_name: input_tensor})
        elapsed_ms = (time.perf_counter() - started) * 1000
        return self._decode_outputs(outputs, w, h, elapsed_ms)

    def status(self) -> dict:
        return {
            "ready": self.ready,
            "model_path_configured": self.model_path is not None,
            "model_name": self.model_path.name if self.model_path else None,
            "provider": "CPUExecutionProvider",
            "version": self.model_version,
        }

    def _preprocess(self, frame: np.ndarray) -> np.ndarray:
        input_meta = self.session.get_inputs()[0] if self.session is not None else None
        shape = list(input_meta.shape) if input_meta is not None else [1, 3, self.input_size or 300, self.input_size or 300]
        input_type = input_meta.type if input_meta is not None else "tensor(float)"
        is_nhwc = len(shape) == 4 and shape[-1] == 3
        if is_nhwc:
            target_h = self.input_size or (shape[1] if isinstance(shape[1], int) else frame.shape[0])
            target_w = self.input_size or (shape[2] if isinstance(shape[2], int) else frame.shape[1])
        else:
            target_h = self.input_size or (shape[2] if isinstance(shape[2], int) else 300)
            target_w = self.input_size or (shape[3] if len(shape) > 3 and isinstance(shape[3], int) else target_h)
        resized = cv2.resize(frame, (int(target_w), int(target_h)))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        if is_nhwc:
            tensor = rgb[None, ...]
        else:
            tensor = np.transpose(rgb, (2, 0, 1))[None, ...]
        if input_type == "tensor(uint8)":
            return tensor.astype("uint8")
        return tensor.astype("float32")

    def _decode_outputs(self, outputs: list[np.ndarray], frame_w: int, frame_h: int, elapsed_ms: float) -> list[VehicleDetection]:
        detections: list[VehicleDetection] = []
        arrays = [np.asarray(output) for output in outputs]
        # Common SSD exported shape: boxes, labels, scores, num_detections.
        if len(arrays) >= 3:
            boxes = np.atleast_2d(np.squeeze(arrays[0]))
            labels = np.atleast_1d(np.squeeze(arrays[1]).astype("int64"))
            scores = np.atleast_1d(np.squeeze(arrays[2]).astype("float32"))
            if boxes.ndim == 2 and boxes.shape[-1] == 4:
                for box, label, score in zip(boxes, labels, scores):
                    vehicle_class = COCO_VEHICLE_CLASSES.get(int(label))
                    if vehicle_class not in self.enabled_classes or float(score) < self.confidence_threshold:
                        continue
                    y1, x1, y2, x2 = box
                    if max(box) <= 1.5:
                        x1, x2 = x1 * frame_w, x2 * frame_w
                        y1, y2 = y1 * frame_h, y2 * frame_h
                    bbox = BoundingBox(int(x1), int(y1), max(1, int(x2 - x1)), max(1, int(y2 - y1))).clipped(frame_w, frame_h)
                    detections.append(VehicleDetection(bbox, vehicle_class, float(score), (frame_w, frame_h), elapsed_ms))
        if not detections and len(arrays) == 1:
            # YOLO-like fallback: [N, 6] -> x1,y1,x2,y2,score,class_id
            rows = np.squeeze(arrays[0])
            if rows.ndim == 2 and rows.shape[-1] >= 6:
                for row in rows:
                    x1, y1, x2, y2, score, class_id = row[:6]
                    vehicle_class = COCO_VEHICLE_CLASSES.get(int(class_id), "car")
                    if vehicle_class not in self.enabled_classes or float(score) < self.confidence_threshold:
                        continue
                    bbox = BoundingBox(int(x1), int(y1), max(1, int(x2 - x1)), max(1, int(y2 - y1))).clipped(frame_w, frame_h)
                    detections.append(VehicleDetection(bbox, vehicle_class, float(score), (frame_w, frame_h), elapsed_ms))
        return detections


class DisabledVehicleDetector:
    model_version = "disabled"

    @property
    def ready(self) -> bool:
        return True

    def load(self) -> None:
        return None

    def detect(self, frame: np.ndarray) -> list[VehicleDetection]:
        h, w = frame.shape[:2]
        return [VehicleDetection(BoundingBox(0, 0, w, h), "unknown", 1.0, (w, h), 0.0)]

    def status(self) -> dict:
        return {"ready": True, "model_path_configured": False, "model_name": None, "provider": "disabled", "version": "disabled"}
