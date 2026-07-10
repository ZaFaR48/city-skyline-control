from __future__ import annotations

import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.alpr.ocr_engine import RapidOCREngine
from app.alpr.perspective import four_point_transform
from app.alpr.tajik_normalizer import TajikPlateNormalizer
from app.alpr.tajik_validator import TajikPlateValidator
from app.alpr.vehicle_detector import ONNXVehicleDetector, VehicleDetectorError
from app.models_runtime.checksums import sha256_file

ROOT = Path(__file__).resolve().parents[1]


def synthetic_plate(text: str = "1234AB01", angle: float = 0.0) -> np.ndarray:
    image = np.full((120, 420, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (5, 5), (415, 115), (0, 0, 0), 3)
    cv2.putText(image, text, (28, 82), cv2.FONT_HERSHEY_SIMPLEX, 2.1, (0, 0, 0), 5, cv2.LINE_AA)
    if not angle:
        return image
    matrix = cv2.getRotationMatrix2D((210, 60), angle, 1.0)
    return cv2.warpAffine(image, matrix, (420, 120), borderValue=(255, 255, 255))


def create_detector_fixture(path: Path) -> None:
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    input_tensor = helper.make_tensor_value_info("images", TensorProto.FLOAT, [1, 3, 300, 300])
    boxes = numpy_helper.from_array(np.array([[[0.1, 0.1, 0.8, 0.8]]], dtype=np.float32), name="boxes")
    labels = numpy_helper.from_array(np.array([[3]], dtype=np.int64), name="labels")
    scores = numpy_helper.from_array(np.array([[0.95]], dtype=np.float32), name="scores")
    graph = helper.make_graph(
        [
            helper.make_node("Constant", [], ["boxes_out"], value=boxes),
            helper.make_node("Constant", [], ["labels_out"], value=labels),
            helper.make_node("Constant", [], ["scores_out"], value=scores),
        ],
        "detector_fixture",
        [input_tensor],
        [
            helper.make_tensor_value_info("boxes_out", TensorProto.FLOAT, [1, 1, 4]),
            helper.make_tensor_value_info("labels_out", TensorProto.INT64, [1, 1]),
            helper.make_tensor_value_info("scores_out", TensorProto.FLOAT, [1, 1]),
        ],
    )
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 17)])
    model.ir_version = 10
    onnx.save(model, path)


def test_python_310_compatibility_no_strenum() -> None:
    for path in (ROOT / "app").rglob("*.py"):
        assert "StrEnum" not in path.read_text()


def test_vehicle_model_loading_and_real_onnx_inference(tmp_path: Path) -> None:
    model_path = tmp_path / "vehicle_fixture.onnx"
    create_detector_fixture(model_path)
    detector = ONNXVehicleDetector(model_path, expected_sha256=sha256_file(model_path))

    detections = detector.detect(np.zeros((300, 300, 3), dtype=np.uint8))

    assert detector.ready is True
    assert detections
    assert detections[0].vehicle_class == "car"
    assert detections[0].confidence >= 0.9


def test_model_checksum_failure(tmp_path: Path) -> None:
    model_path = tmp_path / "vehicle_fixture.onnx"
    create_detector_fixture(model_path)
    detector = ONNXVehicleDetector(model_path, expected_sha256="0" * 64)

    with pytest.raises(VehicleDetectorError):
        detector.load()


def test_missing_model_failure(tmp_path: Path) -> None:
    detector = ONNXVehicleDetector(tmp_path / "missing.onnx")

    with pytest.raises(VehicleDetectorError):
        detector.load()


def test_real_rapidocr_on_synthetic_plate() -> None:
    image = synthetic_plate()
    ocr = RapidOCREngine(Path("/tmp/nonexistent"), min_confidence=0.0)

    result = ocr.recognize(image)
    normalized = TajikPlateNormalizer().normalize(result.text if result else "")

    assert ocr.ready is True
    assert result is not None
    assert result.text
    assert normalized.canonical_text


def test_perspective_corrected_ocr() -> None:
    image = synthetic_plate()
    points = np.array([[18, 18], [390, 8], [410, 108], [10, 115]], dtype=np.float32)
    corrected = four_point_transform(image, points)
    ocr = RapidOCREngine(Path("/tmp/nonexistent"), min_confidence=0.0)

    result = ocr.recognize(corrected)

    assert result is not None
    assert result.text


def test_tajik_canonical_normalization_and_context_confusions() -> None:
    normalized = TajikPlateNormalizer().normalize("I234A8O1")

    assert normalized.canonical_text == "1234AB01"
    assert normalized.normalization_changes


def test_known_and_unknown_format_validation() -> None:
    validator = TajikPlateValidator()

    assert validator.validate("1234AB01").plate_format == "private_standard"
    unknown = validator.validate("ABCD123")
    assert unknown.plate_format == "unknown"
    assert unknown.status == "needs_review"


def test_archive_contains_no_env_or_runtime_data() -> None:
    archives = sorted((ROOT / "dist-pilot").glob("*.tar.gz"))
    if not archives:
        pytest.skip("No release archive built in this workspace")
    with tarfile.open(archives[-1]) as tar:
        names = tar.getnames()
    assert not any(name.endswith("/.env") for name in names)
    assert not any(any(part in {"data", "logs", "queue", "snapshots", "frames"} for part in Path(name).parts) for name in names)
