from __future__ import annotations

import httpx
from typing import Any, Optional


CREDENTIAL_PATTERNS = [
    "wms_live_sk_", "tms_cs_", "tkt_prod_", "kestrel-tms-agent",
    "svc-wms-integration", "e81c05a9f2b64d7e", "4f8a2b91c7e3d5a6",
    "9d1e4770b2af8c35",
]


class BaseClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> tuple[int, Any]:
        client = await self._get_client()
        response = await client.request(
            method, path, headers=headers, params=params, json=json_body,
        )
        status = response.status_code
        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        data = _strip_credentials(data)
        return status, data

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def _strip_credentials(data: Any) -> Any:
    if isinstance(data, str):
        for pattern in CREDENTIAL_PATTERNS:
            if pattern in data:
                data = data.replace(pattern, "[REDACTED]")
        return data
    if isinstance(data, dict):
        return {k: _strip_credentials(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_strip_credentials(item) for item in data]
    return data
