"""Structured JSON audit logger.

Writes one JSON object per line to a log file and keeps an in-memory
buffer for test assertions.  All writes are serialised with an asyncio
lock so concurrent coroutines do not interleave output.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Optional

import aiofiles

from kestrel_gateway.models.audit_record import AuditRecord


class AuditLogger:
    """Append-only JSON-lines audit logger."""

    def __init__(self, log_path: str) -> None:
        self._log_path = Path(log_path)
        self._lock = asyncio.Lock()
        self._buffer: list[AuditRecord] = []

    async def log(self, record: AuditRecord) -> None:
        """Write *record* as a JSON line to the log file and the in-memory buffer."""
        line = record.model_dump_json() + "\n"
        async with self._lock:
            self._buffer.append(record)
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(self._log_path, mode="a", encoding="utf-8") as fh:
                await fh.write(line)

    async def get_records(self, filters: dict[str, Any] | None = None) -> list[AuditRecord]:
        """Return records from the in-memory buffer, optionally filtered.

        *filters* is a simple ``{field: value}`` dict.  A record matches
        when **all** specified fields equal the given value.
        """
        if filters is None:
            return list(self._buffer)

        result: list[AuditRecord] = []
        for rec in self._buffer:
            dump = rec.model_dump()
            if all(dump.get(k) == v for k, v in filters.items()):
                result.append(rec)
        return result

    async def flush_buffer(self) -> None:
        """Clear the in-memory buffer (useful in tests)."""
        async with self._lock:
            self._buffer.clear()
