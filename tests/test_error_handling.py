"""
Tests for gateway error handling.

Covers:
- Unknown / unregistered tool names
- Missing caller identity
- Upstream HTTP errors (404, etc.)
- State resilience after sequential errors
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Unknown tool
# ---------------------------------------------------------------------------

async def test_unknown_tool_returns_authorization_denied(gateway, warehouse_ops_site_01):
    """A tool that is not in TOOL_ACL returns AUTHORIZATION_DENIED (NOT_REGISTERED)."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call("nonexistent_tool", {})
    assert result["code"] == "AUTHORIZATION_DENIED"
    assert "not available" in result["error"].lower() or "not registered" in result.get("error", "").lower()


async def test_unexposed_tool_ticket_delete_returns_authorization_denied(gateway, warehouse_ops_site_01):
    """ticket_delete is never exposed; every team gets AUTHORIZATION_DENIED."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call("ticket_delete", {})
    assert result["code"] == "AUTHORIZATION_DENIED"


async def test_unexposed_tool_contract_search_returns_authorization_denied(gateway, finance_analytics):
    """contract_search is never exposed; every team gets AUTHORIZATION_DENIED."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call("contract_search", {"text": "test"})
    assert result["code"] == "AUTHORIZATION_DENIED"


async def test_unexposed_tool_wms_stock_adjust_returns_authorization_denied(gateway, warehouse_ops_site_01):
    """wms_stock_adjust is never exposed."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call("wms_stock_adjust", {"sku": "SKU-A1001", "site": "SITE-01", "delta": 10})
    assert result["code"] == "AUTHORIZATION_DENIED"


async def test_unexposed_tool_wms_bin_move_returns_authorization_denied(gateway, warehouse_ops_site_01):
    """wms_bin_move is never exposed."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call("wms_bin_move", {"sku": "SKU-A1001", "from_bin": "A-01-01", "to_bin": "A-01-02", "qty": 5})
    assert result["code"] == "AUTHORIZATION_DENIED"


# ---------------------------------------------------------------------------
# No caller identity
# ---------------------------------------------------------------------------

async def test_no_caller_identity_returns_no_identity(gateway):
    """When no caller is set, the gateway must return NO_IDENTITY."""
    # Deliberately do NOT call gateway.set_caller(...)
    gateway._caller = None
    result = await gateway._handle_tool_call("wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"})
    assert result["code"] == "NO_IDENTITY"
    assert "caller" in result["error"].lower() or "identity" in result["error"].lower()


# ---------------------------------------------------------------------------
# Upstream HTTP errors
# ---------------------------------------------------------------------------

async def test_upstream_404_returns_upstream_error(gateway, warehouse_ops_site_01):
    """A 404 from the WMS stub surfaces as UPSTREAM_ERROR."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-NONEXISTENT", "site": "SITE-01"}
    )
    assert result["code"] == "UPSTREAM_ERROR"
    assert "404" in result["error"]


async def test_upstream_404_booking_not_found(gateway, transport_planning):
    """A non-existent booking reference returns UPSTREAM_ERROR."""
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "tms_booking_lookup", {"booking_ref": "BK-NONEXISTENT"}
    )
    assert result["code"] == "UPSTREAM_ERROR"
    assert "404" in result["error"]


async def test_upstream_404_contract_not_found(gateway, finance_analytics):
    """A non-existent customer contract returns UPSTREAM_ERROR."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-NONEXISTENT"}
    )
    assert result["code"] == "UPSTREAM_ERROR"
    assert "404" in result["error"]


async def test_upstream_error_is_not_retriable_for_4xx(gateway, warehouse_ops_site_01):
    """Client errors (4xx) are not marked as retriable."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-NONEXISTENT", "site": "SITE-01"}
    )
    assert result["code"] == "UPSTREAM_ERROR"
    assert result.get("retriable") is False


# ---------------------------------------------------------------------------
# State resilience — errors must not corrupt subsequent calls
# ---------------------------------------------------------------------------

async def test_errors_do_not_corrupt_subsequent_calls(gateway, warehouse_ops_site_01):
    """Multiple failing calls must not prevent a later successful call."""
    gateway.set_caller(warehouse_ops_site_01)

    # Trigger several errors
    r1 = await gateway._handle_tool_call("nonexistent_tool", {})
    assert r1["code"] == "AUTHORIZATION_DENIED"

    r2 = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-NONEXISTENT", "site": "SITE-01"}
    )
    assert r2["code"] == "UPSTREAM_ERROR"

    # Now a valid call should still succeed
    r3 = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"}
    )
    assert r3.get("success") is True
    assert r3.get("_content_boundary") is True


async def test_identity_switch_between_calls(gateway, warehouse_ops_site_01, finance_analytics):
    """Switching caller identity between calls works correctly."""
    gateway.set_caller(warehouse_ops_site_01)
    r1 = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"}
    )
    assert r1.get("success") is True

    # Switch identity — finance cannot access ticket_search
    gateway.set_caller(finance_analytics)
    r2 = await gateway._handle_tool_call("ticket_search", {"query": "test"})
    assert r2["code"] == "AUTHORIZATION_DENIED"

    # Switch back — warehouse ops can still use wms_stock_lookup
    gateway.set_caller(warehouse_ops_site_01)
    r3 = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"}
    )
    assert r3.get("success") is True
