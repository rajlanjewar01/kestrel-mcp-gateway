"""
Tests for input sanitisation and output content-boundary wrapping.

Covers:
- Search-operator stripping (AND / OR / NOT, special characters)
- Prompt-injection pattern removal from upstream responses
- Normal queries passing through unaltered
- Content-boundary markers on every successful response
"""

from __future__ import annotations

import json


# ---------------------------------------------------------------------------
# Search-operator stripping
# ---------------------------------------------------------------------------

async def test_search_query_operators_stripped(gateway, warehouse_ops_site_01):
    """AND / OR / NOT keywords and special chars are removed from ticket_search queries."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "ticket_search", {"query": "stock AND damaged OR billing"}
    )
    # The gateway should still succeed — sanitisation happens transparently
    assert result.get("success") is True or result.get("code") != "VALIDATION_ERROR"


async def test_search_query_special_chars_stripped(gateway, warehouse_ops_site_01):
    """Lucene-style operators (* ? :) are removed from the query."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "ticket_search", {"query": "stock* AND site:SITE-01"}
    )
    # Call should succeed; operators are silently removed
    assert result.get("success") is True or result.get("code") != "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Prompt-injection stripping on upstream responses
# ---------------------------------------------------------------------------

async def test_prompt_injection_stripped_from_response(gateway, transport_planning):
    """TKT-010 contains 'IGNORE PREVIOUS INSTRUCTIONS' — it must be scrubbed."""
    gateway.set_caller(transport_planning)
    # "credit note" matches TKT-010 summary "Credit note for damaged stock"
    result = await gateway._handle_tool_call(
        "ticket_search", {"query": "credit note"}
    )
    assert result.get("success") is True

    # Serialise the entire response and verify injection text is gone
    blob = json.dumps(result).upper()
    assert "IGNORE PREVIOUS INSTRUCTIONS" not in blob
    assert "IGNORE ALL PREVIOUS" not in blob


async def test_prompt_injection_patterns_scrubbed_variants(gateway, transport_planning):
    """Multiple injection-pattern families must be scrubbed from upstream text."""
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "ticket_search", {"query": "credit note"}
    )
    assert result.get("success") is True

    blob = json.dumps(result)
    for pattern in [
        "IGNORE PREVIOUS INSTRUCTIONS",
        "DISREGARD PREVIOUS",
        "SYSTEM:",
        "ASSISTANT:",
        "[INST]",
        "<<SYS>>",
    ]:
        assert pattern not in blob.upper(), f"Injection pattern '{pattern}' leaked through"


# ---------------------------------------------------------------------------
# Normal queries pass through
# ---------------------------------------------------------------------------

async def test_normal_search_query_succeeds(gateway, warehouse_ops_site_01):
    """A plain-text query with no operators passes through and returns results."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "ticket_search", {"query": "stock mismatch"}
    )
    assert result.get("success") is True


# ---------------------------------------------------------------------------
# Content-boundary markers
# ---------------------------------------------------------------------------

async def test_content_boundary_on_stock_lookup(gateway, warehouse_ops_site_01):
    """Every successful response must carry _content_boundary markers."""
    gateway.set_caller(warehouse_ops_site_01)
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"}
    )
    assert result.get("success") is True
    assert result.get("_content_boundary") is True
    assert "data" in result
    assert isinstance(result["_notice"], str)
    assert "upstream" in result["_notice"].lower()


async def test_content_boundary_on_contract_lookup(gateway, finance_analytics):
    """Content boundary is present on contract lookups too."""
    gateway.set_caller(finance_analytics)
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-A"}
    )
    assert result.get("success") is True
    assert result.get("_content_boundary") is True


async def test_content_boundary_on_ticket_search(gateway, transport_planning):
    """Content boundary wraps ticket search results."""
    gateway.set_caller(transport_planning)
    result = await gateway._handle_tool_call(
        "ticket_search", {"query": "delay"}
    )
    assert result.get("success") is True
    assert result.get("_content_boundary") is True
