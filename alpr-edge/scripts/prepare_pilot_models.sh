#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${ROOT_DIR}/models-pilot"
VEHICLE_URL="https://huggingface.co/onnxmodelzoo/ssd_mobilenet_v1_12/resolve/main/ssd_mobilenet_v1_12.onnx"

mkdir -p "${MODEL_DIR}/vehicle" "${MODEL_DIR}/plate" "${MODEL_DIR}/ocr" "${MODEL_DIR}/licenses"

if [[ ! -f "${MODEL_DIR}/vehicle/ssd_mobilenet_v1_12.onnx" ]]; then
  curl -L --fail --retry 3 --connect-timeout 20 \
    -o "${MODEL_DIR}/vehicle/ssd_mobilenet_v1_12.onnx" \
    "${VEHICLE_URL}"
fi

python3 - <<'PY'
from pathlib import Path
import json
import shutil

from app.models_runtime.checksums import sha256_file

try:
    import rapidocr_onnxruntime
except ImportError as exc:
    raise SystemExit("[FAIL] rapidocr_onnxruntime must be installed before preparing OCR models") from exc

root = Path(rapidocr_onnxruntime.__file__).parent
model_dir = Path("models-pilot")
files = {
    "ch_PP-OCRv4_det_infer.onnx": "det.onnx",
    "ch_PP-OCRv4_rec_infer.onnx": "rec.onnx",
    "ch_ppocr_mobile_v2.0_cls_infer.onnx": "cls.onnx",
}
entries = []
for source_name, destination_name in files.items():
    source = root / "models" / source_name
    destination = model_dir / "ocr" / destination_name
    shutil.copy2(source, destination)
    entries.append({
        "name": f"RapidOCR {source_name}",
        "role": "ocr",
        "path": f"ocr/{destination_name}",
        "sha256": sha256_file(destination),
        "source_url": "https://github.com/RapidAI/RapidOCR",
        "license": "Apache-2.0 project; OCR model copyright documented by RapidAI/Baidu",
        "version": "rapidocr-onnxruntime-1.4.4",
    })
vehicle = model_dir / "vehicle" / "ssd_mobilenet_v1_12.onnx"
entries.append({
    "name": "SSD-MobileNetV1-12 ONNX Model Zoo",
    "role": "vehicle",
    "path": "vehicle/ssd_mobilenet_v1_12.onnx",
    "sha256": sha256_file(vehicle),
    "source_url": "https://huggingface.co/onnxmodelzoo/ssd_mobilenet_v1_12",
    "license": "Apache-2.0 badge on Hugging Face model card; model card text includes upstream license notes",
    "version": "1.9.0-opset12",
})
(model_dir / "licenses" / "RAPIDOCR.md").write_text(
    "RapidOCR project: Apache-2.0. OCR model copyright is documented by RapidAI; "
    "models copied from rapidocr-onnxruntime 1.4.4 installed wheel for offline station use. "
    "Source: https://github.com/RapidAI/RapidOCR\n",
    encoding="utf-8",
)
(model_dir / "licenses" / "SSD_MOBILENET_V1_12.md").write_text(
    "SSD-MobileNetV1-12 ONNX Model Zoo mirror. Source: "
    "https://huggingface.co/onnxmodelzoo/ssd_mobilenet_v1_12. The model card shows an Apache-2.0 "
    "badge and includes upstream license notes; verify before production use.\n",
    encoding="utf-8",
)
(model_dir / "licenses" / "PLATE_DETECTOR.md").write_text(
    "No dedicated Tajik plate detector is included in this pilot pack. The application uses a real "
    "OpenCV hybrid geometric/OCR plate candidate detector until a licensed Tajik-specific detector "
    "is trained and verified.\n",
    encoding="utf-8",
)
manifest = {
    "models": entries,
    "notes": ["No dedicated plate detector included; hybrid OpenCV fallback is used."],
}
(model_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
with (model_dir / "SHA256SUMS").open("w", encoding="utf-8") as handle:
    for path in sorted([*list((model_dir / "ocr").glob("*.onnx")), vehicle]):
        handle.write(f"{sha256_file(path)}  {path.relative_to(model_dir)}\n")
PY

"${ROOT_DIR}/scripts/verify_pilot_models.sh" "${MODEL_DIR}"
