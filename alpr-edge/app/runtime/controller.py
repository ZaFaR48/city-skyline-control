from __future__ import annotations

import threading

from app.config import AppConfig
from app.runtime.worker import EdgeWorker


class RuntimeController:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._worker: EdgeWorker | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> dict:
        if self.running:
            return {"running": True, "message": "Runtime worker already running in API process."}
        self._worker = EdgeWorker(self.config)
        self._thread = threading.Thread(target=self._worker.run_forever, kwargs={"poll_seconds": 5.0}, daemon=True)
        self._thread.start()
        return {"running": True, "message": "Runtime worker started in API process."}

    def stop(self) -> dict:
        if not self.running or self._worker is None:
            return {"running": False, "message": "Runtime worker is not running in API process."}
        self._worker.request_stop()
        assert self._thread is not None
        self._thread.join(timeout=10)
        return {"running": self.running, "message": "Runtime worker stop requested."}
