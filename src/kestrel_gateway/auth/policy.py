from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from kestrel_gateway.auth.context import CallerIdentity
from kestrel_gateway.config.teams import TOOL_ACL, ROW_SCOPE_FIELD, Team


@dataclass
class AuthzDecision:
    allowed: bool
    rule: str
    reason: Optional[str] = None


def authorize(caller: CallerIdentity, tool_name: str, arguments: dict[str, Any]) -> AuthzDecision:
    # Layer 1: tool-level ACL
    allowed_teams = TOOL_ACL.get(tool_name)
    if allowed_teams is None:
        return AuthzDecision(
            allowed=False,
            rule=f"tool:{tool_name}:NOT_REGISTERED",
            reason=f"Tool '{tool_name}' is not available through this gateway",
        )

    if caller.team not in allowed_teams:
        return AuthzDecision(
            allowed=False,
            rule=f"acl:{caller.team.value}:{tool_name}:DENY",
            reason=f"Team '{caller.team.value}' is not authorized to call '{tool_name}'",
        )

    # Layer 2: row-level scope
    scope_field = ROW_SCOPE_FIELD.get(caller.team)

    if scope_field == "site" and caller.site:
        site_arg = arguments.get("site")
        if site_arg and site_arg != caller.site:
            return AuthzDecision(
                allowed=False,
                rule=f"row_scope:site:{caller.site}:MISMATCH:{site_arg}",
                reason=f"Warehouse Ops caller at {caller.site} cannot access data for {site_arg}",
            )

    if scope_field == "customer_id" and caller.customer_ids:
        customer_arg = arguments.get("customer_id")
        if customer_arg and customer_arg not in caller.customer_ids:
            return AuthzDecision(
                allowed=False,
                rule=f"row_scope:customer_id:{caller.customer_ids}:MISMATCH:{customer_arg}",
                reason=f"Customer Service caller scoped to {caller.customer_ids} cannot access customer '{customer_arg}'",
            )

    scope_desc = _scope_description(caller, arguments)
    return AuthzDecision(
        allowed=True,
        rule=f"acl:{caller.team.value}:{tool_name}:ALLOW+{scope_desc}",
    )


def enforce_scope(caller: CallerIdentity, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    scope_field = ROW_SCOPE_FIELD.get(caller.team)

    if scope_field == "site" and caller.site:
        if "site" in _tool_site_params(tool_name):
            arguments = {**arguments, "site": caller.site}

    return arguments


def _tool_site_params(tool_name: str) -> set[str]:
    site_tools = {
        "wms_stock_lookup", "ticket_search", "ticket_create",
        "tms_dock_schedule", "tms_booking_create",
    }
    if tool_name in site_tools:
        return {"site"}
    return set()


def _scope_description(caller: CallerIdentity, arguments: dict[str, Any]) -> str:
    scope_field = ROW_SCOPE_FIELD.get(caller.team)
    if scope_field == "site" and caller.site:
        return f"row_scope:site={caller.site}:MATCH"
    if scope_field == "customer_id" and caller.customer_ids:
        cid = arguments.get("customer_id", "any")
        return f"row_scope:customer={cid}:MATCH"
    return "row_scope:unrestricted"
