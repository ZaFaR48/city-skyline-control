from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class EventUploader:
    def __init__(
        self,
        central_api_url: str | None,
        token: str | None,
        timeout_seconds: float,
    ) -> None:
        self.central_api_url = central_api_url.rstrip("/") if central_api_url else None
        self.token = token
        self.timeout_seconds = timeout_seconds

    @property
    def is_configured(self) -> bool:
        return self.central_api_url is not None

    def upload(self, event: dict[str, Any]) -> bool:
        if not self.is_configured:
            logger.info("Central API not configured; event remains local")
            return False

        assert self.central_api_url is not None
        url = f"{self.central_api_url}/api/alpr/events"
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = requests.post(
                url,
                json=event,
                headers=headers,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Failed to upload ALPR event: %s", exc)
            return False

        logger.info("Uploaded ALPR event to central API")
        return True
