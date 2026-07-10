from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import uuid4

from app.models import PlateEvent

logger = logging.getLogger(__name__)


class OfflineEventQueue:
    def __init__(self, queue_dir: Path) -> None:
        self.queue_dir = queue_dir
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def enqueue(self, event: PlateEvent) -> Path:
        filename = f"{event.timestamp.strftime('%Y%m%dT%H%M%S%fZ')}_{uuid4().hex}.json"
        path = self.queue_dir / filename
        with path.open("w", encoding="utf-8") as file:
            json.dump(event.to_dict(), file, ensure_ascii=False, indent=2)
        logger.info("Queued event for later upload: %s", path)
        return path

    def pending_files(self) -> list[Path]:
        return sorted(self.queue_dir.glob("*.json"))

    def load_file(self, path: Path) -> dict:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def remove(self, path: Path) -> None:
        path.unlink(missing_ok=True)
        logger.info("Removed uploaded queue file: %s", path)
