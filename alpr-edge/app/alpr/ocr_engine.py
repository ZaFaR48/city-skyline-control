from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from app.alpr.models import OCRText
from app.alpr.preprocessing import preprocessing_variants


class OCREngineError(RuntimeError):
    pass


class RapidOCREngine:
    def __init__(
        self,
        model_dir: Path,
        min_confidence: float = 0.45,
        max_variants: int = 5,
        allowed_characters: str = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    ) -> None:
        self.model_dir = model_dir
        self.min_confidence = min_confidence
        self.max_variants = max_variants
        self.allowed_characters = allowed_characters
        self.engine = None
        self.model_version = "rapidocr-onnxruntime"

    @property
    def ready(self) -> bool:
        return self.engine is not None

    def load(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise OCREngineError("rapidocr-onnxruntime is not installed") from exc
        kwargs = {}
        if self.model_dir.exists():
            det = self.model_dir / "det.onnx"
            rec = self.model_dir / "rec.onnx"
            cls = self.model_dir / "cls.onnx"
            keys = self.model_dir / "dict.txt"
            if det.exists():
                kwargs["det_model_path"] = str(det)
            if rec.exists():
                kwargs["rec_model_path"] = str(rec)
            if cls.exists():
                kwargs["cls_model_path"] = str(cls)
            if keys.exists():
                kwargs["rec_keys_path"] = str(keys)
        self.engine = RapidOCR(**kwargs)

    def recognize(self, plate_crop: np.ndarray) -> OCRText | None:
        if self.engine is None:
            self.load()
        assert self.engine is not None
        best: OCRText | None = None
        for variant_name, image in preprocessing_variants(plate_crop, self.max_variants):
            started = time.perf_counter()
            result, _ = self.engine(image)
            elapsed_ms = (time.perf_counter() - started) * 1000
            if not result:
                continue
            text = "".join(str(item[1]) for item in result)
            confidence_values = [float(item[2]) for item in result if len(item) >= 3]
            confidence = sum(confidence_values) / max(1, len(confidence_values))
            filtered = "".join(ch for ch in text.upper() if ch in self.allowed_characters)
            if not filtered:
                continue
            candidate = OCRText(filtered, confidence, [item[0] for item in result], elapsed_ms, variant_name)
            if best is None or candidate.confidence > best.confidence:
                best = candidate
        if best is None or best.confidence < self.min_confidence:
            return best
        return best

    def status(self) -> dict:
        return {
            "ready": self.ready,
            "backend": "rapidocr",
            "model_dir": "configured" if self.model_dir.exists() else "package-default",
            "version": self.model_version,
        }
