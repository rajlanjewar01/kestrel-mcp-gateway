"""
Tests for the kill-switch mechanism.

Covers tool-level, team-level, and gateway-level disabling, plus re-enabling.
"""


class TestKillSwitchTool:
    """Disable / re-enable a single tool."""

    async def test_disabled_tool_returns_kill_switch_active(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        gateway.kill_switch.disable_tool("wms_stock_lookup")
        try:
            result = await gateway._handle_tool_call(
                "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
            )
            assert result.get("code") == "KILL_SWITCH_ACTIVE"
        finally:
            gateway.kill_switch.enable_tool("wms_stock_lookup")

    async def test_reenabled_tool_succeeds(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        gateway.kill_switch.disable_tool("wms_stock_lookup")
        gateway.kill_switch.enable_tool("wms_stock_lookup")

        result = await gateway._handle_tool_call(
            "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
        )
        assert result.get("success") is True

    async def test_other_tools_unaffected_by_single_tool_disable(self, gateway, transport_planning):
        """Disabling one tool does not block a different tool."""
        gateway.set_caller(transport_planning)
        gateway.kill_switch.disable_tool("wms_stock_lookup")
        try:
            result = await gateway._handle_tool_call(
                "tms_booking_lookup", {"booking_ref": "BK-001"},
            )
            assert result.get("code") != "KILL_SWITCH_ACTIVE"
        finally:
            gateway.kill_switch.enable_tool("wms_stock_lookup")


class TestKillSwitchTeam:
    """Disable / re-enable an entire team."""

    async def test_disabled_team_returns_kill_switch_active(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        gateway.kill_switch.disable_team("warehouse_ops")
        try:
            result = await gateway._handle_tool_call(
                "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
            )
            assert result.get("code") == "KILL_SWITCH_ACTIVE"
        finally:
            gateway.kill_switch.enable_team("warehouse_ops")

    async def test_other_team_unaffected(self, gateway, transport_planning):
        """A different team can still call tools when warehouse_ops is disabled."""
        gateway.kill_switch.disable_team("warehouse_ops")
        try:
            gateway.set_caller(transport_planning)
            result = await gateway._handle_tool_call(
                "tms_booking_lookup", {"booking_ref": "BK-001"},
            )
            assert result.get("code") != "KILL_SWITCH_ACTIVE"
        finally:
            gateway.kill_switch.enable_team("warehouse_ops")

    async def test_reenabled_team_succeeds(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        gateway.kill_switch.disable_team("warehouse_ops")
        gateway.kill_switch.enable_team("warehouse_ops")

        result = await gateway._handle_tool_call(
            "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
        )
        assert result.get("success") is True


class TestKillSwitchGateway:
    """Disable / re-enable the entire gateway."""

    async def test_disabled_gateway_blocks_all_teams(
        self, gateway, warehouse_ops_site_01, transport_planning, finance_analytics,
    ):
        gateway.kill_switch.disable_gateway()
        try:
            for caller, tool, args in [
                (warehouse_ops_site_01, "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"}),
                (transport_planning, "tms_booking_lookup", {"booking_ref": "BK-001"}),
                (finance_analytics, "contract_lookup", {"customer_id": "CUST-A"}),
            ]:
                gateway.set_caller(caller)
                result = await gateway._handle_tool_call(tool, args)
                assert result.get("code") == "KILL_SWITCH_ACTIVE", (
                    f"Expected KILL_SWITCH_ACTIVE for {tool} but got {result.get('code')}"
                )
        finally:
            gateway.kill_switch.enable_gateway()

    async def test_reenabled_gateway_succeeds(self, gateway, warehouse_ops_site_01):
        gateway.set_caller(warehouse_ops_site_01)
        gateway.kill_switch.disable_gateway()
        gateway.kill_switch.enable_gateway()

        result = await gateway._handle_tool_call(
            "wms_stock_lookup", {"sku": "SKU-A1001", "site": "SITE-01"},
        )
        assert result.get("success") is True
