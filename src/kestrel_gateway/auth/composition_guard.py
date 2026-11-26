from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from kestrel_gateway.auth.context import CallerIdentity
from kestrel_gateway.config.teams import Team


@dataclass
class CompositionViolation:
    description: str
    tools_involved: list[str]
    risk: str


class CompositionGuard:
    def __init__(self):
        self._session_history: dict[str, list[str]] = defaultdict(list)

    def check_pre_call(
        self, caller: CallerIdentity, tool_name: str, arguments: dict[str, Any]
    ) -> Optional[CompositionViolation]:
        session_key = f"{caller.team.value}:{caller.user_id}"
        history = self._session_history[session_key]

        if caller.team == Team.CUSTOMER_SERVICE:
            # Customer Service accessing rate_card_lookup should already be blocked at ACL,
            # but as defense in depth check here too.
            if tool_name == "rate_card_lookup":
                return CompositionViolation(
                    description="Customer Service cannot access rate cards",
                    tools_involved=[tool_name],
                    risk="cross_customer_rate_disclosure",
                )

            # If Customer Service has been reading contracts AND searching tickets,
            # flag potential cross-customer data assembly
            if tool_name == "ticket_search" and "contract_lookup" in history:
                pass  # Allowed, but ticket_search results are filtered by customer

        self._session_history[session_key].append(tool_name)
        return None

    def filter_results(
        self, caller: CallerIdentity, tool_name: str, results: Any
    ) -> tuple[Any, bool]:
        if caller.team == Team.CUSTOMER_SERVICE and tool_name == "ticket_search":
            if isinstance(results, list):
                filtered = [
                    r for r in results
                    if _ticket_matches_customer(r, caller.customer_ids)
                ]
                was_filtered = len(filtered) != len(results)
                return filtered, was_filtered
        return results, False

    def reset_session(self, caller: CallerIdentity) -> None:
        session_key = f"{caller.team.value}:{caller.user_id}"
        self._session_history.pop(session_key, None)


def _ticket_matches_customer(
    ticket: dict, customer_ids: Optional[list[str]]
) -> bool:
    if not customer_ids:
        return True
    ticket_customer = ticket.get("customer_id")
    if ticket_customer is None:
        # Tickets without customer_id are internal — allow
        return True
    return ticket_customer in customer_ids
