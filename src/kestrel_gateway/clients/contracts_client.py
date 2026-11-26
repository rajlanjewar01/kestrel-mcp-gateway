from __future__ import annotations

from typing import Any

from kestrel_gateway.clients.base import BaseClient


class ContractsClient(BaseClient):
    def __init__(self, base_url: str, cert_path: str = "", key_path: str = ""):
        super().__init__(base_url)
        # In production this would use mTLS; in test mode we use a header
        self._headers = {"X-Client-Cert": "valid"}

    async def contract_lookup(self, customer_id: str) -> tuple[int, Any]:
        return await self._request(
            "GET", f"/contract/{customer_id}", headers=self._headers,
        )

    async def rate_card_lookup(self, customer_id: str) -> tuple[int, Any]:
        return await self._request(
            "GET", f"/rate-card/{customer_id}", headers=self._headers,
        )
