from __future__ import annotations

from typing import Any

import httpx

from config import settings


class BackendAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class BackendAPI:
    def __init__(self) -> None:
        self._access_token: str | None = None

    async def _login(self) -> str:
        payload = {
            "username": settings.jwt_username,
            "password": settings.jwt_password,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"{settings.api_url}/api/auth/login", json=payload)
        if response.status_code >= 400:
            raise BackendAPIError("Backend login failed", response.status_code)
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise BackendAPIError("Backend login response did not include an access token")
        self._access_token = token
        return token

    async def _token(self) -> str:
        if self._access_token:
            return self._access_token
        return await self._login()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        retry: bool = True,
        **kwargs: Any,
    ) -> Any:
        token = await self._token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.request(
                method,
                f"{settings.api_url}{path}",
                headers=headers,
                **kwargs,
            )

        if response.status_code == 401 and retry:
            self._access_token = None
            return await self._request(method, path, retry=False, **kwargs)

        if response.status_code >= 400:
            raise BackendAPIError(_error_detail(response), response.status_code)

        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def search_stations(self, query: str) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/stations", params={"q": query, "limit": 10})
        return list(data or [])

    async def create_station(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request("POST", "/api/stations", json=payload)
        return dict(data or {})

    async def create_camera(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = await self._request("POST", "/api/cameras", json=payload)
        return dict(data or {})

    async def update_rustdesk(self, station_id: int, rustdesk_id: str) -> None:
        await self._request(
            "PUT",
            f"/api/rustdesk/{station_id}",
            params={"rustdesk_id": rustdesk_id},
        )


def _error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return f"Backend request failed with HTTP {response.status_code}"

    detail = data.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            loc = ".".join(str(part) for part in item.get("loc", []))
            msg = item.get("msg", "validation error")
            parts.append(f"{loc}: {msg}" if loc else msg)
        return "; ".join(parts) or f"Backend request failed with HTTP {response.status_code}"
    return f"Backend request failed with HTTP {response.status_code}"


api = BackendAPI()
