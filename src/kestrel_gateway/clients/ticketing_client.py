from __future__ import annotations

from typing import Any

from kestrel_gateway.clients.base import BaseClient


class TicketingClient(BaseClient):
    def __init__(self, base_url: str, bearer_token: str):
        super().__init__(base_url)
        self._headers = {"Authorization": f"Bearer {bearer_token}"}

    async def search(self, query: str, status: str | None = None, site: str | None = None) -> tuple[int, Any]:
        params: dict[str, str] = {"query": query}
        if status:
            params["status"] = status
        if site:
            params["site"] = site
        return await self._request("GET", "/tickets/search", headers=self._headers, params=params)

    async def create(self, site: str, category: str, summary: str, detail: str) -> tuple[int, Any]:
        return await self._request(
            "POST", "/tickets", headers=self._headers,
            json_body={"site": site, "category": category, "summary": summary, "detail": detail},
        )

    async def comment(self, ticket_id: str, body: str) -> tuple[int, Any]:
        return await self._request(
            "POST", f"/tickets/{ticket_id}/comment", headers=self._headers,
            json_body={"body": body},
        )

    async def close(self, ticket_id: str, resolution: str) -> tuple[int, Any]:
        return await self._request(
            "POST", f"/tickets/{ticket_id}/close", headers=self._headers,
            json_body={"resolution": resolution},
        )
