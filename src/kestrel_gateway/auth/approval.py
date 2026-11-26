from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class ApprovalRequest:
    approval_id: str
    tool: str
    team: str
    user_id: str
    arguments: dict[str, Any]
    reason: str
    created_at: str


@dataclass
class ApprovalDecision:
    approval_id: str
    approved: bool
    decided_by: str
    decided_at: str
    reason: Optional[str] = None


class ApprovalGate:
    def __init__(self):
        self._pending: dict[str, ApprovalRequest] = {}
        self._decisions: dict[str, ApprovalDecision] = {}
        self._auto_approve: bool = False

    def request_approval(
        self, tool: str, team: str, user_id: str, arguments: dict[str, Any], reason: str
    ) -> ApprovalRequest:
        req = ApprovalRequest(
            approval_id=str(uuid.uuid4()),
            tool=tool,
            team=team,
            user_id=user_id,
            arguments=arguments,
            reason=reason,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._pending[req.approval_id] = req
        return req

    def decide(self, approval_id: str, approved: bool, decided_by: str, reason: Optional[str] = None) -> ApprovalDecision:
        decision = ApprovalDecision(
            approval_id=approval_id,
            approved=approved,
            decided_by=decided_by,
            decided_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
        )
        self._decisions[approval_id] = decision
        self._pending.pop(approval_id, None)
        return decision

    def get_decision(self, approval_id: str) -> Optional[ApprovalDecision]:
        return self._decisions.get(approval_id)

    def set_auto_approve(self, enabled: bool) -> None:
        self._auto_approve = enabled

    @property
    def auto_approve(self) -> bool:
        return self._auto_approve
