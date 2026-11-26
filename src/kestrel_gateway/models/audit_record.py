from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request_id: str
    team: str
    user_id: str
    tool: str
    arguments: dict[str, Any]
    authz_decision: str
    authz_rule: str
    upstream_system: str
    upstream_status: Optional[int] = None
    result_filtered: bool = False
    result_withheld: bool = False
    approval_required: bool = False
    approval_decision: Optional[str] = None
    approval_id: Optional[str] = None
    kill_switch_blocked: bool = False
    rate_limit_blocked: bool = False
    error: Optional[str] = None
    duration_ms: Optional[float] = None
