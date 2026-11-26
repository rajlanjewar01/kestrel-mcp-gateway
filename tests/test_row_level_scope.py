"""
Row-level scope tests for the Kestrel MCP Gateway.

Verifies that:
- WAREHOUSE_OPS callers are restricted to their assigned site.
- CUSTOMER_SERVICE callers are restricted to their assigned customer_ids.
- TRANSPORT_PLANNING and FINANCE_ANALYTICS have unrestricted scope.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# WAREHOUSE_OPS site scope
# ---------------------------------------------------------------------------

async def test_warehouse_ops_can_read_own_site_stock(gateway, warehouse_ops_site_01):
    """WAREHOUSE_OPS at SITE-01 can look up stock at SITE-01."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
    )
    assert result.get("success") is True


async def test_warehouse_ops_cannot_read_other_site_stock(gateway, warehouse_ops_site_01):
    """WAREHOUSE_OPS at SITE-01 is denied stock lookup at SITE-02."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-B2001", "site": "SITE-02"},
    )
    assert result.get("code") == "AUTHORIZATION_DENIED"


async def test_warehouse_ops_site02_can_read_own_site_stock(gateway, warehouse_ops_site_02):
    """WAREHOUSE_OPS at SITE-02 can look up stock at SITE-02."""
    gateway.set_caller(warehouse_ops_site_02)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-B2001", "site": "SITE-02"},
    )
    assert result.get("success") is True


async def test_warehouse_ops_site02_cannot_read_site01_stock(gateway, warehouse_ops_site_02):
    """WAREHOUSE_OPS at SITE-02 is denied stock lookup at SITE-01."""
    gateway.set_caller(warehouse_ops_site_02)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
    )
    assert result.get("code") == "AUTHORIZATION_DENIED"


async def test_warehouse_ops_can_search_tickets_own_site(gateway, warehouse_ops_site_01):
    """WAREHOUSE_OPS at SITE-01 can search tickets at SITE-01."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "ticket_search", {"query": "stock", "site": "SITE-01"},
    )
    assert result.get("success") is True


async def test_warehouse_ops_cannot_search_tickets_other_site(gateway, warehouse_ops_site_01):
    """WAREHOUSE_OPS at SITE-01 is denied ticket search at SITE-02."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "ticket_search", {"query": "stock", "site": "SITE-02"},
    )
    assert result.get("code") == "AUTHORIZATION_DENIED"


# ---------------------------------------------------------------------------
# CUSTOMER_SERVICE customer scope
# ---------------------------------------------------------------------------

async def test_customer_service_can_lookup_own_customer_contract(
    gateway, customer_service_cust_a,
):
    """CUSTOMER_SERVICE scoped to CUST-A can look up CUST-A contract."""
    gateway.set_caller(customer_service_cust_a)
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("success") is True


async def test_customer_service_cannot_lookup_other_customer_contract(
    gateway, customer_service_cust_a,
):
    """CUSTOMER_SERVICE scoped to CUST-A is denied CUST-B contract lookup."""
    gateway.set_caller(customer_service_cust_a)
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-B"},
    )
    assert result.get("code") == "AUTHORIZATION_DENIED"


async def test_customer_service_cust_b_can_lookup_own_contract(
    gateway, customer_service_cust_b,
):
    """CUSTOMER_SERVICE scoped to CUST-B can look up CUST-B contract."""
    gateway.set_caller(customer_service_cust_b)
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-B"},
    )
    assert result.get("success") is True


async def test_customer_service_cust_b_cannot_lookup_cust_a_contract(
    gateway, customer_service_cust_b,
):
    """CUSTOMER_SERVICE scoped to CUST-B is denied CUST-A contract lookup."""
    gateway.set_caller(customer_service_cust_b)
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("code") == "AUTHORIZATION_DENIED"


# ---------------------------------------------------------------------------
# TRANSPORT_PLANNING unrestricted scope
# ---------------------------------------------------------------------------

async def test_transport_planning_can_read_any_site_stock(gateway, transport_planning):
    """TRANSPORT_PLANNING has no site restriction -- can read SITE-02 stock."""
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-B2001", "site": "SITE-02"},
    )
    assert result.get("success") is True


async def test_transport_planning_can_read_any_site_dock_schedule(gateway, transport_planning):
    """TRANSPORT_PLANNING has no site restriction -- can read SITE-02 dock schedule."""
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "tms_dock_schedule", {"site": "SITE-02", "date_from": "2026-11-27", "date_to": "2026-11-27"},
    )
    assert result.get("success") is True


async def test_transport_planning_can_read_site03_stock(gateway, transport_planning):
    """TRANSPORT_PLANNING can read SITE-03 stock without restriction."""
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-C3001", "site": "SITE-03"},
    )
    assert result.get("success") is True


# ---------------------------------------------------------------------------
# FINANCE_ANALYTICS unrestricted scope
# ---------------------------------------------------------------------------

async def test_finance_can_read_any_customer_contract(gateway, finance_analytics):
    """FINANCE_ANALYTICS has no customer restriction -- can read CUST-B contract."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-B"},
    )
    assert result.get("success") is True


async def test_finance_can_read_any_customer_rate_card(gateway, finance_analytics):
    """FINANCE_ANALYTICS can read CUST-A rate card."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(
        "rate_card_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("success") is True


async def test_finance_can_read_different_customer_contract(gateway, finance_analytics):
    """FINANCE_ANALYTICS can read CUST-C contract (no customer scoping)."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-C"},
    )
    assert result.get("success") is True
