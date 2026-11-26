"""
Composition guard tests for the Kestrel MCP Gateway.

Verifies that:
- Unexposed tools (contract_search, ticket_delete, wms_stock_adjust, wms_bin_move)
  return AUTHORIZATION_DENIED for every team.
- Customer Service ticket_search results are filtered to only their customer.
- Finance CAN access rate_card_lookup.
- Customer Service CANNOT access rate_card_lookup (ACL + composition guard defense-in-depth).
"""

from __future__ import annotations

import pytest

from kestrel_gateway.auth.context import CallerIdentity
from kestrel_gateway.config.teams import Team


# ---------------------------------------------------------------------------
# Unexposed tools -- not registered in TOOL_ACL, should return NOT_REGISTERED
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool_name", [
    "contract_search",
    "ticket_delete",
    "wms_stock_adjust",
    "wms_bin_move",
])
async def test_unregistered_tool_denied_for_warehouse_ops(
    gateway, warehouse_ops_site_01, tool_name,
):
    """Unregistered tools return AUTHORIZATION_DENIED for WAREHOUSE_OPS."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(tool_name, {})
    assert result.get("code") == "AUTHORIZATION_DENIED"
    assert "not available" in result.get("error", "").lower()


@pytest.mark.parametrize("tool_name", [
    "contract_search",
    "ticket_delete",
    "wms_stock_adjust",
    "wms_bin_move",
])
async def test_unregistered_tool_denied_for_transport_planning(
    gateway, transport_planning, tool_name,
):
    """Unregistered tools return AUTHORIZATION_DENIED for TRANSPORT_PLANNING."""
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(tool_name, {})
    assert result.get("code") == "AUTHORIZATION_DENIED"


@pytest.mark.parametrize("tool_name", [
    "contract_search",
    "ticket_delete",
    "wms_stock_adjust",
    "wms_bin_move",
])
async def test_unregistered_tool_denied_for_customer_service(
    gateway, customer_service_cust_a, tool_name,
):
    """Unregistered tools return AUTHORIZATION_DENIED for CUSTOMER_SERVICE."""
    gateway.set_caller(customer_service_cust_a)
    result = await gateway._handle_tool_call(tool_name, {})
    assert result.get("code") == "AUTHORIZATION_DENIED"


@pytest.mark.parametrize("tool_name", [
    "contract_search",
    "ticket_delete",
    "wms_stock_adjust",
    "wms_bin_move",
])
async def test_unregistered_tool_denied_for_finance(
    gateway, finance_analytics, tool_name,
):
    """Unregistered tools return AUTHORIZATION_DENIED for FINANCE_ANALYTICS."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(tool_name, {})
    assert result.get("code") == "AUTHORIZATION_DENIED"


# ---------------------------------------------------------------------------
# Customer Service ticket_search result filtering
# ---------------------------------------------------------------------------

async def test_customer_service_ticket_search_succeeds(
    gateway, customer_service_cust_a,
):
    """Customer Service CUST-A can perform ticket_search."""
    gateway.set_caller(customer_service_cust_a)
    result = await gateway._handle_tool_call(
        "ticket_search", {"query": "stock"},
    )
    assert result.get("success") is True


def test_composition_guard_filters_list_by_customer():
    """CompositionGuard.filter_results strips tickets not matching the caller's customers."""
    from kestrel_gateway.auth.composition_guard import CompositionGuard

    guard = CompositionGuard()
    caller = CallerIdentity(team=Team.CUSTOMER_SERVICE, user_id="cs-01", customer_ids=["CUST-A"])

    # When data is a list, filter_results should keep only CUST-A tickets
    raw = [
        {"ticket_id": "TKT-001", "customer_id": "CUST-A"},
        {"ticket_id": "TKT-003", "customer_id": "CUST-B"},
        {"ticket_id": "TKT-006", "customer_id": "CUST-C"},
        {"ticket_id": "TKT-009", "customer_id": "CUST-A"},
    ]
    filtered, was_filtered = guard.filter_results(caller, "ticket_search", raw)
    assert was_filtered is True
    assert all(t["customer_id"] == "CUST-A" for t in filtered)
    assert len(filtered) == 2


def test_composition_guard_no_filter_for_non_customer_service():
    """TRANSPORT_PLANNING ticket_search results are not filtered."""
    from kestrel_gateway.auth.composition_guard import CompositionGuard

    guard = CompositionGuard()
    caller = CallerIdentity(team=Team.TRANSPORT_PLANNING, user_id="tp-01")

    raw = [
        {"ticket_id": "TKT-001", "customer_id": "CUST-A"},
        {"ticket_id": "TKT-003", "customer_id": "CUST-B"},
    ]
    filtered, was_filtered = guard.filter_results(caller, "ticket_search", raw)
    assert was_filtered is False
    assert len(filtered) == 2


# ---------------------------------------------------------------------------
# rate_card_lookup access
# ---------------------------------------------------------------------------

async def test_finance_can_access_rate_card_lookup(gateway, finance_analytics):
    """FINANCE_ANALYTICS is authorized for rate_card_lookup."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(
        "rate_card_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("success") is True


async def test_customer_service_cannot_access_rate_card_lookup(
    gateway, customer_service_cust_a,
):
    """CUSTOMER_SERVICE is denied rate_card_lookup (ACL block + composition guard)."""
    gateway.set_caller(customer_service_cust_a)
    result = await gateway._handle_tool_call(
        "rate_card_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("code") == "AUTHORIZATION_DENIED"


async def test_warehouse_ops_cannot_access_rate_card_lookup(
    gateway, warehouse_ops_site_01,
):
    """WAREHOUSE_OPS is denied rate_card_lookup."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "rate_card_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("code") == "AUTHORIZATION_DENIED"


async def test_transport_planning_cannot_access_rate_card_lookup(
    gateway, transport_planning,
):
    """TRANSPORT_PLANNING is denied rate_card_lookup."""
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "rate_card_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("code") == "AUTHORIZATION_DENIED"
