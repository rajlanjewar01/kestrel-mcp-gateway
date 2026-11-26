"""
Tests for structured audit logging.

Every gateway operation — allowed, denied, rate-limited, or kill-switch-blocked —
must produce an AuditRecord with the required fields.
"""


class TestAuditSuccessfulCall:
    """A successful tool call must produce a complete audit record."""

    async def test_audit_record_on_success(self, gateway, warehouse_ops_site_01):
        await gateway.audit_logger.flush_buffer()
        gateway.set_caller(warehouse_ops_site_01)

        result = await gateway._handle_tool_call(
            "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
        )
        assert result.get("success") is True

        records = await gateway.audit_logger.get_records()
        assert len(records) >= 1
        rec = records[-1]

        assert rec.team == "warehouse_ops"
        assert rec.user_id == "wh-user-01"
        assert rec.tool == "wms_stock_lookup"
        assert rec.authz_decision == "ALLOW"
        assert rec.upstream_system == "wms"
        assert "sku" in rec.arguments
        assert "site" in rec.arguments

    async def test_audit_record_has_all_required_fields(self, gateway, warehouse_ops_site_01):
        """Verify that no structurally required field is missing or None."""
        await gateway.audit_logger.flush_buffer()
        gateway.set_caller(warehouse_ops_site_01)

        await gateway._handle_tool_call(
            "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
        )

        records = await gateway.audit_logger.get_records()
        rec = records[-1]
        dump = rec.model_dump()

        for field in [
            "timestamp", "request_id", "team", "user_id", "tool",
            "arguments", "authz_decision", "authz_rule", "upstream_system",
        ]:
            assert dump.get(field) is not None, f"Required audit field '{field}' is None"

    async def test_audit_record_upstream_status_on_success(self, gateway, warehouse_ops_site_01):
        await gateway.audit_logger.flush_buffer()
        gateway.set_caller(warehouse_ops_site_01)

        await gateway._handle_tool_call(
            "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
        )

        records = await gateway.audit_logger.get_records()
        rec = records[-1]
        assert rec.upstream_status == 200


class TestAuditDeniedCall:
    """A denied call must still produce an audit record."""

    async def test_authz_denied_produces_audit_record(self, gateway, warehouse_ops_site_01):
        await gateway.audit_logger.flush_buffer()
        gateway.set_caller(warehouse_ops_site_01)

        result = await gateway._handle_tool_call(
            "tms_booking_create",
            {"site": "SITE-01", "carrier": "DHL", "window": "2026-12-01T08:00:00Z", "load_ref": "LOAD-9999"},
        )
        assert result.get("code") == "AUTHORIZATION_DENIED"

        records = await gateway.audit_logger.get_records()
        assert len(records) >= 1
        rec = records[-1]
        assert rec.authz_decision == "DENY"
        assert rec.tool == "tms_booking_create"
        assert rec.team == "warehouse_ops"

    async def test_unregistered_tool_produces_audit_record(self, gateway, warehouse_ops_site_01):
        await gateway.audit_logger.flush_buffer()
        gateway.set_caller(warehouse_ops_site_01)

        await gateway._handle_tool_call("ticket_delete", {"ticket_id": "TKT-001"})

        records = await gateway.audit_logger.get_records()
        assert len(records) >= 1
        rec = records[-1]
        assert rec.authz_decision == "DENY"
        assert "NOT_REGISTERED" in rec.authz_rule


class TestAuditKillSwitchBlocked:
    """Kill-switch-blocked calls must have kill_switch_blocked=True."""

    async def test_kill_switch_blocked_audit(self, gateway, warehouse_ops_site_01):
        await gateway.audit_logger.flush_buffer()
        gateway.set_caller(warehouse_ops_site_01)
        gateway.kill_switch.disable_tool("wms_stock_lookup")
        try:
            await gateway._handle_tool_call(
                "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
            )

            records = await gateway.audit_logger.get_records()
            rec = records[-1]
            assert rec.kill_switch_blocked is True
            assert rec.tool == "wms_stock_lookup"
        finally:
            gateway.kill_switch.enable_tool("wms_stock_lookup")


class TestAuditRateLimitBlocked:
    """Rate-limited calls must have rate_limit_blocked=True in the audit record."""

    async def test_rate_limited_call_audit(self, gateway, finance_analytics):
        await gateway.audit_logger.flush_buffer()
        gateway.set_caller(finance_analytics)

        # rate_card_lookup has a per-tool limit of 10 for finance_analytics.
        # Exhaust the limit.
        for _ in range(10):
            await gateway._handle_tool_call("rate_card_lookup", {"customer_id": "CUST-A"})

        await gateway.audit_logger.flush_buffer()

        # Next call should be rate-limited
        result = await gateway._handle_tool_call("rate_card_lookup", {"customer_id": "CUST-A"})
        assert result.get("code") == "RATE_LIMIT_EXCEEDED"

        records = await gateway.audit_logger.get_records()
        rec = records[-1]
        assert rec.rate_limit_blocked is True
        assert rec.tool == "rate_card_lookup"
