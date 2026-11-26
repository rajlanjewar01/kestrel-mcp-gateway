"""
Tests that credentials never leak through tool descriptions, error responses,
or successful data payloads.

The base client strips known credential patterns; these tests confirm that
no pattern reaches the caller.
"""

from __future__ import annotations

import json

from kestrel_gateway.clients.base import CREDENTIAL_PATTERNS
from kestrel_gateway.server import TOOL_DEFINITIONS


# ---------------------------------------------------------------------------
# Tool descriptions
# ---------------------------------------------------------------------------

def test_tool_descriptions_contain_no_credentials():
    """No TOOL_DEFINITION description string may contain a credential pattern."""
    for td in TOOL_DEFINITIONS:
        desc = json.dumps(td)
        for pattern in CREDENTIAL_PATTERNS:
            assert pattern not in desc, (
                f"Credential pattern '{pattern}' found in tool definition '{td['name']}'"
            )


# ---------------------------------------------------------------------------
# Error responses
# ---------------------------------------------------------------------------

async def test_authorization_error_contains_no_credentials(gateway, finance_analytics):
    """An AUTHORIZATION_DENIED response must not leak credential material."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call("ticket_search", {"query": "test"})
    blob = json.dumps(result)
    for pattern in CREDENTIAL_PATTERNS:
        assert pattern not in blob, (
            f"Credential pattern '{pattern}' leaked in authorization error"
        )


async def test_upstream_error_contains_no_credentials(gateway, warehouse_ops_site_01):
    """An UPSTREAM_ERROR (e.g. 404) must not leak credential material."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-NONEXISTENT", "site": "SITE-01"}
    )
    blob = json.dumps(result)
    for pattern in CREDENTIAL_PATTERNS:
        assert pattern not in blob, (
            f"Credential pattern '{pattern}' leaked in upstream error"
        )


# ---------------------------------------------------------------------------
# Successful responses
# ---------------------------------------------------------------------------

async def test_successful_wms_response_contains_no_credentials(gateway, warehouse_ops_site_01):
    """A successful WMS stock lookup must not contain credential material."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"}
    )
    assert result.get("success") is True
    blob = json.dumps(result)
    for pattern in CREDENTIAL_PATTERNS:
        assert pattern not in blob, (
            f"Credential pattern '{pattern}' leaked in successful WMS response"
        )


async def test_successful_tms_response_contains_no_credentials(gateway, transport_planning):
    """A successful TMS booking lookup must not contain credential material."""
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "tms_booking_lookup", {"booking_ref": "BK-001"}
    )
    assert result.get("success") is True
    blob = json.dumps(result)
    for pattern in CREDENTIAL_PATTERNS:
        assert pattern not in blob, (
            f"Credential pattern '{pattern}' leaked in successful TMS response"
        )


async def test_successful_contract_response_contains_no_credentials(gateway, finance_analytics):
    """A successful contract lookup must not contain credential material."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-A"}
    )
    assert result.get("success") is True
    blob = json.dumps(result)
    for pattern in CREDENTIAL_PATTERNS:
        assert pattern not in blob, (
            f"Credential pattern '{pattern}' leaked in successful contract response"
        )


async def test_successful_rate_card_response_contains_no_credentials(gateway, finance_analytics):
    """Rate card data (commercially sensitive) must not leak credential material."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(
        "rate_card_lookup", {"customer_id": "CUST-A"}
    )
    assert result.get("success") is True
    blob = json.dumps(result)
    for pattern in CREDENTIAL_PATTERNS:
        assert pattern not in blob, (
            f"Credential pattern '{pattern}' leaked in rate card response"
        )


async def test_successful_ticket_search_contains_no_credentials(gateway, transport_planning):
    """Ticket search results must not contain credential material."""
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "ticket_search", {"query": "delay"}
    )
    assert result.get("success") is True
    blob = json.dumps(result)
    for pattern in CREDENTIAL_PATTERNS:
        assert pattern not in blob, (
            f"Credential pattern '{pattern}' leaked in ticket search response"
        )
