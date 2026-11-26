"""
Tests for the approval gate middleware.

APPROVAL_REQUIRED tools: tms_booking_create, tms_booking_cancel, ticket_close.
When auto_approve is False these must return APPROVAL_REQUIRED.
Read-only tools must never trigger the approval gate.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# booking_create
# ---------------------------------------------------------------------------

async def test_booking_create_requires_approval_when_auto_approve_off(gateway, transport_planning):
    """tms_booking_create returns APPROVAL_REQUIRED when auto_approve is False."""
    gateway.approval_gate.set_auto_approve(False)
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "tms_booking_create",
        {"site": "SITE-01", "carrier": "DHL", "window": "2026-12-01T08:00:00Z", "load_ref": "LOAD-9999"},
    )
    assert result.get("code") == "APPROVAL_REQUIRED"
    assert "approval" in result.get("error", "").lower()


async def test_booking_create_proceeds_when_auto_approve_on(gateway, transport_planning):
    """tms_booking_create bypasses the gate when auto_approve is True."""
    gateway.approval_gate.set_auto_approve(True)
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "tms_booking_create",
        {"site": "SITE-01", "carrier": "DHL", "window": "2026-12-01T08:00:00Z", "load_ref": "LOAD-9999"},
    )
    # Should NOT be blocked by approval gate — it may succeed or hit an upstream
    # issue, but the code must not be APPROVAL_REQUIRED.
    assert result.get("code") != "APPROVAL_REQUIRED"


# ---------------------------------------------------------------------------
# booking_cancel
# ---------------------------------------------------------------------------

async def test_booking_cancel_requires_approval_when_auto_approve_off(gateway, transport_planning):
    """tms_booking_cancel returns APPROVAL_REQUIRED when auto_approve is False."""
    gateway.approval_gate.set_auto_approve(False)
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "tms_booking_cancel",
        {"booking_ref": "BK-003", "reason": "Testing cancellation"},
    )
    assert result.get("code") == "APPROVAL_REQUIRED"


async def test_booking_cancel_proceeds_when_auto_approve_on(gateway, transport_planning):
    """tms_booking_cancel bypasses the gate when auto_approve is True."""
    gateway.approval_gate.set_auto_approve(True)
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "tms_booking_cancel",
        {"booking_ref": "BK-003", "reason": "Testing cancellation"},
    )
    assert result.get("code") != "APPROVAL_REQUIRED"


# ---------------------------------------------------------------------------
# ticket_close
# ---------------------------------------------------------------------------

async def test_ticket_close_requires_approval_when_auto_approve_off(gateway, customer_service_cust_a):
    """ticket_close returns APPROVAL_REQUIRED when auto_approve is False."""
    gateway.approval_gate.set_auto_approve(False)
    gateway.set_caller(customer_service_cust_a)
    result = await gateway._handle_tool_call(
        "ticket_close",
        {"ticket_id": "TKT-001", "resolution": "Resolved during test"},
    )
    assert result.get("code") == "APPROVAL_REQUIRED"


async def test_ticket_close_proceeds_when_auto_approve_on(gateway, customer_service_cust_a):
    """ticket_close bypasses the gate when auto_approve is True."""
    gateway.approval_gate.set_auto_approve(True)
    gateway.set_caller(customer_service_cust_a)
    result = await gateway._handle_tool_call(
        "ticket_close",
        {"ticket_id": "TKT-001", "resolution": "Resolved during test"},
    )
    assert result.get("code") != "APPROVAL_REQUIRED"


# ---------------------------------------------------------------------------
# Read-only tools must never require approval, even with auto_approve off
# ---------------------------------------------------------------------------

async def test_stock_lookup_no_approval_needed(gateway, warehouse_ops_site_01):
    """wms_stock_lookup never triggers the approval gate."""
    gateway.approval_gate.set_auto_approve(False)
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup",
        {"sku": "SKU-A1001", "site": "SITE-01"},
    )
    assert result.get("code") != "APPROVAL_REQUIRED"
    assert result.get("success") is True


async def test_booking_lookup_no_approval_needed(gateway, transport_planning):
    """tms_booking_lookup never triggers the approval gate."""
    gateway.approval_gate.set_auto_approve(False)
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "tms_booking_lookup",
        {"booking_ref": "BK-001"},
    )
    assert result.get("code") != "APPROVAL_REQUIRED"
    assert result.get("success") is True


async def test_contract_lookup_no_approval_needed(gateway, finance_analytics):
    """contract_lookup never triggers the approval gate."""
    gateway.approval_gate.set_auto_approve(False)
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(
        "contract_lookup",
        {"customer_id": "CUST-A"},
    )
    assert result.get("code") != "APPROVAL_REQUIRED"
    assert result.get("success") is True


async def test_ticket_search_no_approval_needed(gateway, customer_service_cust_a):
    """ticket_search never triggers the approval gate."""
    gateway.approval_gate.set_auto_approve(False)
    gateway.set_caller(customer_service_cust_a)
    result = await gateway._handle_tool_call(
        "ticket_search",
        {"query": "delay"},
    )
    assert result.get("code") != "APPROVAL_REQUIRED"
    assert result.get("success") is True


async def test_dock_schedule_no_approval_needed(gateway, transport_planning):
    """tms_dock_schedule never triggers the approval gate."""
    gateway.approval_gate.set_auto_approve(False)
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "tms_dock_schedule",
        {"site": "SITE-01", "date_from": "2026-11-26", "date_to": "2026-11-26"},
    )
    assert result.get("code") != "APPROVAL_REQUIRED"
    assert result.get("success") is True


async def test_rate_card_lookup_no_approval_needed(gateway, finance_analytics):
    """rate_card_lookup never triggers the approval gate."""
    gateway.approval_gate.set_auto_approve(False)
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(
        "rate_card_lookup",
        {"customer_id": "CUST-A"},
    )
    assert result.get("code") != "APPROVAL_REQUIRED"
    assert result.get("success") is True
