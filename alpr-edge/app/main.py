from __future__ import annotations

import logging
import signal
import time
from datetime import datetime, timezone

from app.api_client import EventUploader
from app.camera import RTSPCamera, save_frame
from app.config import load_config
from app.detector import PlateDetector
from app.event_queue import OfflineEventQueue
from app.logger import configure_logging
from app.models import EventStatus, PlateEvent
from app.ocr import PlateOCR

logger = logging.getLogger(__name__)
_running = True


def _handle_shutdown(signum: int, frame: object) -> None:
    del signum, frame
    global _running
    _running = False
    logger.info("Shutdown requested")


def _retry_queued_events(queue: OfflineEventQueue, uploader: EventUploader) -> None:
    if not uploader.is_configured:
        return

    for path in queue.pending_files():
        event = queue.load_file(path)
        if uploader.upload(event):
            queue.remove(path)
        else:
            break


def _build_capture_only_event(
    station_code: str,
    camera_id: str,
    image_path,
    direction: str,
    zone_type: str,
) -> PlateEvent:
    return PlateEvent(
        station_code=station_code,
        camera_id=camera_id,
        timestamp=datetime.now(timezone.utc),
        plate_text=None,
        confidence=None,
        image_path=image_path,
        direction=direction,
        zone_type=zone_type,
        status=EventStatus.NEEDS_REVIEW,
    )


def _build_plate_event(
    station_code: str,
    camera_id: str,
    image_path,
    direction: str,
    zone_type: str,
    plate_text: str,
    confidence: float,
) -> PlateEvent:
    return PlateEvent(
        station_code=station_code,
        camera_id=camera_id,
        timestamp=datetime.now(timezone.utc),
        plate_text=plate_text,
        confidence=confidence,
        image_path=image_path,
        direction=direction,
        zone_type=zone_type,
        status=EventStatus.DETECTED,
    )


def _dispatch_event(event: PlateEvent, queue: OfflineEventQueue, uploader: EventUploader) -> None:
    if not uploader.upload(event.to_dict()):
        queue.enqueue(event)


def main() -> int:
    config = load_config()
    configure_logging(config.log_level)
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    camera = RTSPCamera(config.rtsp_url)
    detector = PlateDetector(config.detector_model_path)
    ocr = PlateOCR(config.ocr_model_path)
    queue = OfflineEventQueue(config.queue_dir)
    uploader = EventUploader(
        config.central_api_url,
        config.central_api_token,
        config.upload_timeout_seconds,
    )

    logger.info("Starting ALPR edge app for station=%s camera=%s", config.station_code, config.camera_id)
    if not config.model_configured:
        logger.info("ALPR model not configured; frame captured only.")

    last_sample_at = 0.0
    last_retry_at = 0.0

    try:
        camera.open()
        while _running:
            frame = camera.read_frame()
            now = time.monotonic()

            if frame is None:
                time.sleep(1)
                continue

            if now - last_retry_at >= config.retry_interval_seconds:
                _retry_queued_events(queue, uploader)
                last_retry_at = now

            if now - last_sample_at < config.sample_interval_seconds:
                continue

            last_sample_at = now
            image_path = save_frame(
                frame,
                config.frame_output_dir,
                config.station_code,
                config.camera_id,
            )
            logger.info("Captured sample frame: %s", image_path)

            if not config.model_configured:
                logger.info("ALPR model not configured; frame captured only.")
                event = _build_capture_only_event(
                    config.station_code,
                    config.camera_id,
                    image_path,
                    config.direction,
                    config.zone_type,
                )
                _dispatch_event(event, queue, uploader)
                continue

            detections = detector.detect(frame)
            logger.info("Detected %d candidate plates", len(detections))
            if not detections:
                event = _build_capture_only_event(
                    config.station_code,
                    config.camera_id,
                    image_path,
                    config.direction,
                    config.zone_type,
                )
                _dispatch_event(event, queue, uploader)
                continue

            for detection in detections:
                x1 = max(detection.x, 0)
                y1 = max(detection.y, 0)
                x2 = max(detection.x + detection.width, x1)
                y2 = max(detection.y + detection.height, y1)
                plate_crop = frame[y1:y2, x1:x2]
                ocr_result = ocr.recognize(plate_crop)
                if ocr_result is None:
                    event = _build_capture_only_event(
                        config.station_code,
                        config.camera_id,
                        image_path,
                        config.direction,
                        config.zone_type,
                    )
                else:
                    event = _build_plate_event(
                        config.station_code,
                        config.camera_id,
                        image_path,
                        config.direction,
                        config.zone_type,
                        ocr_result.plate_text,
                        ocr_result.confidence,
                    )
                _dispatch_event(event, queue, uploader)
    finally:
        camera.close()

    logger.info("ALPR edge app stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
