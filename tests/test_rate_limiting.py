"""
Tests for the per-(team, system) and per-(team, tool) rate limiter.

Key limits from teams.py:
- contracts system: 20 req/min for finance_analytics and customer_service
- rate_card_lookup tool-level limit: 10 req/min for finance_analytics
"""

from __future__ import annotations


async def test_rate_card_tool_limit_exceeded(gateway, finance_analytics):
    """After 10 rate_card_lookup calls the per-tool bucket rejects the 11th."""
    gateway.rate_limiter.reset()
    gateway.set_caller(finance_analytics)

    for i in range(10):
        result = await gateway._handle_tool_call(
            "rate_card_lookup", {"customer_id": "CUST-A"},
        )
        assert result.get("code") != "RATE_LIMIT_EXCEEDED", (
            f"Unexpectedly rate-limited on call {i + 1}"
        )

    # 11th call must be rejected
    result = await gateway._handle_tool_call(
        "rate_card_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("code") == "RATE_LIMIT_EXCEEDED"


async def test_system_level_limit_exceeded(gateway, finance_analytics):
    """After 20 contract_lookup calls the system bucket rejects the 21st."""
    gateway.rate_limiter.reset()
    gateway.set_caller(finance_analytics)

    for i in range(20):
        result = await gateway._handle_tool_call(
            "contract_lookup", {"customer_id": "CUST-A"},
        )
        assert result.get("code") != "RATE_LIMIT_EXCEEDED", (
            f"Unexpectedly rate-limited on call {i + 1}"
        )

    # 21st call must be rejected
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("code") == "RATE_LIMIT_EXCEEDED"


async def test_rate_limit_resets_after_clear(gateway, finance_analytics):
    """After calling reset() on the rate limiter, calls succeed again."""
    gateway.rate_limiter.reset()
    gateway.set_caller(finance_analytics)

    # Exhaust the rate_card_lookup tool limit (10)
    for _ in range(10):
        await gateway._handle_tool_call(
            "rate_card_lookup", {"customer_id": "CUST-A"},
        )

    blocked = await gateway._handle_tool_call(
        "rate_card_lookup", {"customer_id": "CUST-A"},
    )
    assert blocked.get("code") == "RATE_LIMIT_EXCEEDED"

    # Reset and retry
    gateway.rate_limiter.reset()
    result = await gateway._handle_tool_call(
        "rate_card_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("code") != "RATE_LIMIT_EXCEEDED"


async def test_different_teams_have_independent_budgets(
    gateway, finance_analytics, customer_service_cust_a,
):
    """Exhausting one team's budget does not affect another team."""
    gateway.rate_limiter.reset()

    # Exhaust the contracts system budget for finance_analytics (20 req/min)
    gateway.set_caller(finance_analytics)
    for _ in range(20):
        await gateway._handle_tool_call(
            "contract_lookup", {"customer_id": "CUST-A"},
        )

    blocked = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-A"},
    )
    assert blocked.get("code") == "RATE_LIMIT_EXCEEDED"

    # customer_service should still be able to call contract_lookup
    gateway.set_caller(customer_service_cust_a)
    result = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-A"},
    )
    assert result.get("code") != "RATE_LIMIT_EXCEEDED"


async def test_rate_limit_does_not_affect_different_system(gateway, finance_analytics):
    """Exhausting the contracts budget should not affect WMS calls."""
    gateway.rate_limiter.reset()
    gateway.set_caller(finance_analytics)

    # Exhaust contracts system budget
    for _ in range(20):
        await gateway._handle_tool_call(
            "contract_lookup", {"customer_id": "CUST-A"},
        )

    blocked = await gateway._handle_tool_call(
        "contract_lookup", {"customer_id": "CUST-A"},
    )
    assert blocked.get("code") == "RATE_LIMIT_EXCEEDED"

    # WMS is a separate system and should still work
    result = await gateway._handle_tool_call(
        "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
    )
    assert result.get("code") != "RATE_LIMIT_EXCEEDED"
