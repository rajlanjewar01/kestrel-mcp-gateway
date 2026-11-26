from __future__ import annotations

from typing import Any

from kestrel_gateway.clients.base import BaseClient


class WmsClient(BaseClient):
    def __init__(self, base_url: str, api_key: str):
        super().__init__(base_url)
        self._headers = {"X-API-Key": api_key}

    async def stock_lookup(self, sku: str, site: str) -> tuple[int, Any]:
        return await self._request(
            "GET", f"/stock/{sku}", headers=self._headers, params={"site": site},
        )

    async def stock_adjust(self, sku: str, site: str, delta: int, reason: str) -> tuple[int, Any]:
        return await self._request(
            "POST", "/stock/adjust", headers=self._headers,
            json_body={"sku": sku, "site": site, "delta": delta, "reason": reason},
        )

    async def bin_move(self, sku: str, from_bin: str, to_bin: str, qty: int) -> tuple[int, Any]:
        return await self._request(
            "POST", "/bin/move", headers=self._headers,
            json_body={"sku": sku, "from_bin": from_bin, "to_bin": to_bin, "qty": qty},
        )
