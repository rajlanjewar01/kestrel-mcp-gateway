"""
Authorization matrix tests — team x tool ACL.

For every exposed tool: one positive test (authorized team) and one negative
test (unauthorized team).  For every NOT-REGISTERED tool: one test per team
confirming AUTHORIZATION_DENIED.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_authorized(result: dict) -> None:
    """The call was NOT blocked by authorization (may still fail upstream)."""
    assert result.get("code") != "AUTHORIZATION_DENIED", (
        f"Expected authorization to pass but got AUTHORIZATION_DENIED: {result}"
    )


def _assert_denied(result: dict) -> None:
    assert result.get("code") == "AUTHORIZATION_DENIED", (
        f"Expected AUTHORIZATION_DENIED but got: {result}"
    )


# ===================================================================
# wms_stock_lookup — allowed: ALL four teams
# ===================================================================

class TestWmsStockLookup:

    async def test_warehouse_ops_can_stock_lookup(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
        )
        assert result.get("success") is True

    async def test_transport_planning_can_stock_lookup(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
        )
        assert result.get("success") is True

    async def test_customer_service_can_stock_lookup(self, gateway, customer_service_cust_a):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(
            "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
        )
        assert result.get("success") is True

    async def test_finance_can_stock_lookup(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
        )
        assert result.get("success") is True


# ===================================================================
# tms_dock_schedule — allowed: TRANSPORT_PLANNING, FINANCE_ANALYTICS
# ===================================================================

class TestTmsDockSchedule:

    async def test_transport_planning_can_dock_schedule(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "tms_dock_schedule",
            {"site": "SITE-01", "date_from": "2026-11-26", "date_to": "2026-11-26"},
        )
        assert result.get("success") is True

    async def test_finance_can_dock_schedule(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "tms_dock_schedule",
            {"site": "SITE-01", "date_from": "2026-11-26", "date_to": "2026-11-26"},
        )
        assert result.get("success") is True

    async def test_warehouse_ops_cannot_dock_schedule(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "tms_dock_schedule",
            {"site": "SITE-01", "date_from": "2026-11-26", "date_to": "2026-11-26"},
        )
        _assert_denied(result)

    async def test_customer_service_cannot_dock_schedule(self, gateway, customer_service_cust_a):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(
            "tms_dock_schedule",
            {"site": "SITE-01", "date_from": "2026-11-26", "date_to": "2026-11-26"},
        )
        _assert_denied(result)


# ===================================================================
# tms_booking_lookup — allowed: TRANSPORT_PLANNING, FINANCE_ANALYTICS
# ===================================================================

class TestTmsBookingLookup:

    async def test_transport_planning_can_booking_lookup(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "tms_booking_lookup", {"booking_ref": "BK-001"},
        )
        assert result.get("success") is True

    async def test_finance_can_booking_lookup(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "tms_booking_lookup", {"booking_ref": "BK-001"},
        )
        assert result.get("success") is True

    async def test_warehouse_ops_cannot_booking_lookup(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "tms_booking_lookup", {"booking_ref": "BK-001"},
        )
        _assert_denied(result)

    async def test_customer_service_cannot_booking_lookup(self, gateway, customer_service_cust_a):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(
            "tms_booking_lookup", {"booking_ref": "BK-001"},
        )
        _assert_denied(result)


# ===================================================================
# tms_booking_create — allowed: TRANSPORT_PLANNING only
# (approval_required, auto_approve=True in gateway fixture)
# ===================================================================

class TestTmsBookingCreate:

    async def test_transport_planning_can_booking_create(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "tms_booking_create",
            {"site": "SITE-01", "carrier": "DHL", "window": "2026-12-01T08:00:00Z", "load_ref": "LOAD-9001"},
        )
        # May get upstream error due to stub schema mismatch, but NOT authz denied
        _assert_authorized(result)

    async def test_warehouse_ops_cannot_booking_create(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "tms_booking_create",
            {"site": "SITE-01", "carrier": "DHL", "window": "2026-12-01T08:00:00Z", "load_ref": "LOAD-9001"},
        )
        _assert_denied(result)

    async def test_finance_cannot_booking_create(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "tms_booking_create",
            {"site": "SITE-01", "carrier": "DHL", "window": "2026-12-01T08:00:00Z", "load_ref": "LOAD-9001"},
        )
        _assert_denied(result)

    async def test_customer_service_cannot_booking_create(self, gateway, customer_service_cust_a):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(
            "tms_booking_create",
            {"site": "SITE-01", "carrier": "DHL", "window": "2026-12-01T08:00:00Z", "load_ref": "LOAD-9001"},
        )
        _assert_denied(result)


# ===================================================================
# tms_booking_cancel — allowed: TRANSPORT_PLANNING only
# (approval_required, auto_approve=True in gateway fixture)
# ===================================================================

class TestTmsBookingCancel:

    async def test_transport_planning_can_booking_cancel(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "tms_booking_cancel", {"booking_ref": "BK-003", "reason": "Test cancel"},
        )
        _assert_authorized(result)

    async def test_warehouse_ops_cannot_booking_cancel(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "tms_booking_cancel", {"booking_ref": "BK-003", "reason": "Test cancel"},
        )
        _assert_denied(result)

    async def test_finance_cannot_booking_cancel(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "tms_booking_cancel", {"booking_ref": "BK-003", "reason": "Test cancel"},
        )
        _assert_denied(result)

    async def test_customer_service_cannot_booking_cancel(self, gateway, customer_service_cust_a):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(
            "tms_booking_cancel", {"booking_ref": "BK-003", "reason": "Test cancel"},
        )
        _assert_denied(result)


# ===================================================================
# ticket_search — allowed: WAREHOUSE_OPS, TRANSPORT_PLANNING, CUSTOMER_SERVICE
# ===================================================================

class TestTicketSearch:

    async def test_warehouse_ops_can_ticket_search(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "ticket_search", {"query": "stock"},
        )
        assert result.get("success") is True

    async def test_transport_planning_can_ticket_search(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "ticket_search", {"query": "stock"},
        )
        assert result.get("success") is True

    async def test_customer_service_can_ticket_search(self, gateway, customer_service_cust_a):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(
            "ticket_search", {"query": "stock"},
        )
        assert result.get("success") is True

    async def test_finance_cannot_ticket_search(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "ticket_search", {"query": "stock"},
        )
        _assert_denied(result)


# ===================================================================
# ticket_create — allowed: WAREHOUSE_OPS, TRANSPORT_PLANNING, CUSTOMER_SERVICE
# ===================================================================

class TestTicketCreate:

    async def test_warehouse_ops_can_ticket_create(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "ticket_create",
            {"site": "SITE-01", "category": "damaged_goods", "summary": "Test ticket", "detail": "Testing ticket creation"},
        )
        # Upstream stub may need customer_id — but authz passes before dispatch
        _assert_authorized(result)

    async def test_transport_planning_can_ticket_create(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "ticket_create",
            {"site": "SITE-01", "category": "damaged_goods", "summary": "Test ticket", "detail": "Testing ticket creation"},
        )
        _assert_authorized(result)

    async def test_finance_cannot_ticket_create(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "ticket_create",
            {"site": "SITE-01", "category": "damaged_goods", "summary": "Test ticket", "detail": "Testing ticket creation"},
        )
        _assert_denied(result)


# ===================================================================
# ticket_comment — allowed: WAREHOUSE_OPS, CUSTOMER_SERVICE
# ===================================================================

class TestTicketComment:

    async def test_warehouse_ops_can_ticket_comment(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "ticket_comment", {"ticket_id": "TKT-001", "body": "Test comment"},
        )
        # Upstream stub expects different field names, may get upstream error
        _assert_authorized(result)

    async def test_customer_service_can_ticket_comment(self, gateway, customer_service_cust_a):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(
            "ticket_comment", {"ticket_id": "TKT-001", "body": "Test comment"},
        )
        _assert_authorized(result)

    async def test_transport_planning_cannot_ticket_comment(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "ticket_comment", {"ticket_id": "TKT-001", "body": "Test comment"},
        )
        _assert_denied(result)

    async def test_finance_cannot_ticket_comment(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "ticket_comment", {"ticket_id": "TKT-001", "body": "Test comment"},
        )
        _assert_denied(result)


# ===================================================================
# ticket_close — allowed: CUSTOMER_SERVICE only
# (approval_required, auto_approve=True in gateway fixture)
# ===================================================================

class TestTicketClose:

    async def test_customer_service_can_ticket_close(self, gateway, customer_service_cust_a):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(
            "ticket_close", {"ticket_id": "TKT-002", "resolution": "Resolved in test"},
        )
        _assert_authorized(result)

    async def test_warehouse_ops_cannot_ticket_close(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "ticket_close", {"ticket_id": "TKT-002", "resolution": "Resolved in test"},
        )
        _assert_denied(result)

    async def test_transport_planning_cannot_ticket_close(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "ticket_close", {"ticket_id": "TKT-002", "resolution": "Resolved in test"},
        )
        _assert_denied(result)

    async def test_finance_cannot_ticket_close(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "ticket_close", {"ticket_id": "TKT-002", "resolution": "Resolved in test"},
        )
        _assert_denied(result)


# ===================================================================
# contract_lookup — allowed: CUSTOMER_SERVICE, FINANCE_ANALYTICS
# ===================================================================

class TestContractLookup:

    async def test_customer_service_can_contract_lookup(self, gateway, customer_service_cust_a):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(
            "contract_lookup", {"customer_id": "CUST-A"},
        )
        assert result.get("success") is True

    async def test_finance_can_contract_lookup(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "contract_lookup", {"customer_id": "CUST-A"},
        )
        assert result.get("success") is True

    async def test_warehouse_ops_cannot_contract_lookup(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "contract_lookup", {"customer_id": "CUST-A"},
        )
        _assert_denied(result)

    async def test_transport_planning_cannot_contract_lookup(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "contract_lookup", {"customer_id": "CUST-A"},
        )
        _assert_denied(result)


# ===================================================================
# rate_card_lookup — allowed: FINANCE_ANALYTICS only
# ===================================================================

class TestRateCardLookup:

    async def test_finance_can_rate_card_lookup(self, gateway, finance_analytics):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(
            "rate_card_lookup", {"customer_id": "CUST-A"},
        )
        assert result.get("success") is True

    async def test_warehouse_ops_cannot_rate_card_lookup(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(
            "rate_card_lookup", {"customer_id": "CUST-A"},
        )
        _assert_denied(result)

    async def test_transport_planning_cannot_rate_card_lookup(self, gateway, transport_planning):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(
            "rate_card_lookup", {"customer_id": "CUST-A"},
        )
        _assert_denied(result)

    async def test_customer_service_cannot_rate_card_lookup(self, gateway, customer_service_cust_a):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(
            "rate_card_lookup", {"customer_id": "CUST-A"},
        )
        _assert_denied(result)


# ===================================================================
# NOT REGISTERED tools — denied for every team
# ===================================================================

class TestNotRegisteredTools:
    """Tools that exist in upstream stubs but are not exposed by the gateway."""

    @pytest.mark.parametrize("tool_name", [
        "ticket_delete",
        "contract_search",
        "wms_stock_adjust",
        "wms_bin_move",
    ])
    async def test_warehouse_ops_denied_unregistered(self, gateway, warehouse_ops_site_01, tool_name):
        gateway.set_caller(warehouse_ops_site_01)
        result = await gateway._handle_tool_call(tool_name, {})
        _assert_denied(result)

    @pytest.mark.parametrize("tool_name", [
        "ticket_delete",
        "contract_search",
        "wms_stock_adjust",
        "wms_bin_move",
    ])
    async def test_transport_planning_denied_unregistered(self, gateway, transport_planning, tool_name):
        gateway.set_caller(transport_planning)
        result = await gateway._handle_tool_call(tool_name, {})
        _assert_denied(result)

    @pytest.mark.parametrize("tool_name", [
        "ticket_delete",
        "contract_search",
        "wms_stock_adjust",
        "wms_bin_move",
    ])
    async def test_customer_service_denied_unregistered(self, gateway, customer_service_cust_a, tool_name):
        gateway.set_caller(customer_service_cust_a)
        result = await gateway._handle_tool_call(tool_name, {})
        _assert_denied(result)

    @pytest.mark.parametrize("tool_name", [
        "ticket_delete",
        "contract_search",
        "wms_stock_adjust",
        "wms_bin_move",
    ])
    async def test_finance_denied_unregistered(self, gateway, finance_analytics, tool_name):
        gateway.set_caller(finance_analytics)
        result = await gateway._handle_tool_call(tool_name, {})
        _assert_denied(result)
