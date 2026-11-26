from __future__ import annotations

import time
from typing import Any, Optional

from kestrel_gateway.clients.base import BaseClient


class TmsClient(BaseClient):
    def __init__(self, base_url: str, client_id: str, client_secret: str):
        super().__init__(base_url)
        self._client_id = client_id
        self._client_secret = client_secret
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0

    async def _ensure_token(self) -> str:
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token

        status, data = await self._request(
            "POST", "/oauth/token",
            json_body={"client_id": self._client_id, "client_secret": self._client_secret},
        )
        if status == 200:
            self._access_token = data.get("access_token", "")
            self._token_expiry = time.time() + data.get("expires_in", 3600) - 60
        return self._access_token or ""

    async def _auth_headers(self) -> dict[str, str]:
        token = await self._ensure_token()
        return {"Authorization": f"Bearer {token}"}

    async def dock_schedule(self, site: str, date_from: str, date_to: str) -> tuple[int, Any]:
        headers = await self._auth_headers()
        return await self._request(
            "GET", "/dock-schedule", headers=headers,
            params={"site": site, "from": date_from, "to": date_to},
        )

    async def booking_lookup(self, booking_ref: str) -> tuple[int, Any]:
        headers = await self._auth_headers()
        return await self._request("GET", f"/booking/{booking_ref}", headers=headers)

    async def booking_create(self, site: str, carrier: str, window: str, load_ref: str) -> tuple[int, Any]:
        headers = await self._auth_headers()
        return await self._request(
            "POST", "/booking", headers=headers,
            json_body={"site": site, "carrier": carrier, "window": window, "load_ref": load_ref},
        )

    async def booking_cancel(self, booking_ref: str, reason: str) -> tuple[int, Any]:
        headers = await self._auth_headers()
        return await self._request(
            "POST", f"/booking/{booking_ref}/cancel", headers=headers,
            json_body={"reason": reason},
        )
