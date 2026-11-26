from __future__ import annotations

import json
import time
import uuid
from typing import Any

from mcp.server.lowlevel import Server
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, TextContent, Tool

from kestrel_gateway.auth.approval import ApprovalGate
from kestrel_gateway.auth.composition_guard import CompositionGuard
from kestrel_gateway.auth.context import CallerIdentity
from kestrel_gateway.auth.policy import authorize, enforce_scope
from kestrel_gateway.clients.contracts_client import ContractsClient
from kestrel_gateway.clients.ticketing_client import TicketingClient
from kestrel_gateway.clients.tms_client import TmsClient
from kestrel_gateway.clients.wms_client import WmsClient
from kestrel_gateway.config.kill_switch import KillSwitch
from kestrel_gateway.config.settings import GatewaySettings
from kestrel_gateway.config.teams import APPROVAL_REQUIRED, TOOL_TO_SYSTEM
from kestrel_gateway.middleware.audit import AuditLogger
from kestrel_gateway.middleware.rate_limiter import RateLimiter
from kestrel_gateway.middleware.sanitizer import Sanitizer
from kestrel_gateway.models.audit_record import AuditRecord
from kestrel_gateway.models.errors import (
    approval_required_error,
    authorization_error,
    kill_switch_error,
    rate_limit_error,
    upstream_error,
    validation_error,
)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "wms_stock_lookup",
        "description": "[READ] Look up current stock level for a SKU at a specific warehouse site. Returns quantity on hand, bin location, and last count date.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "Stock keeping unit identifier"},
                "site": {"type": "string", "description": "Warehouse site code (e.g. SITE-01)", "enum": [f"SITE-{i:02d}" for i in range(1, 12)]},
            },
            "required": ["sku", "site"],
        },
    },
    {
        "name": "tms_dock_schedule",
        "description": "[READ] View dock schedule showing booked and available slots for a site over a date range.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "site": {"type": "string", "description": "Warehouse site code", "enum": [f"SITE-{i:02d}" for i in range(1, 12)]},
                "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
            },
            "required": ["site", "date_from", "date_to"],
        },
    },
    {
        "name": "tms_booking_lookup",
        "description": "[READ] Look up details of a carrier booking by reference number. Returns carrier, vehicle, dock window, and status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "booking_ref": {"type": "string", "description": "Booking reference number"},
            },
            "required": ["booking_ref"],
        },
    },
    {
        "name": "tms_booking_create",
        "description": "[WRITE — FINANCIALLY COMMITTING] Create a carrier booking at a dock slot. Cancellation within 4 hours of the window incurs carrier charges (GBP 180-450). Requires human approval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "site": {"type": "string", "description": "Warehouse site code", "enum": [f"SITE-{i:02d}" for i in range(1, 12)]},
                "carrier": {"type": "string", "description": "Carrier name"},
                "window": {"type": "string", "description": "Requested dock window (ISO datetime)"},
                "load_ref": {"type": "string", "description": "Load reference identifier"},
            },
            "required": ["site", "carrier", "window", "load_ref"],
        },
    },
    {
        "name": "tms_booking_cancel",
        "description": "[WRITE — FINANCIALLY COMMITTING] Cancel a carrier booking. Cancellation within 4 hours of the window incurs carrier charges (GBP 180-450). Requires human approval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "booking_ref": {"type": "string", "description": "Booking reference to cancel"},
                "reason": {"type": "string", "description": "Reason for cancellation"},
            },
            "required": ["booking_ref", "reason"],
        },
    },
    {
        "name": "ticket_search",
        "description": "[READ] Search exception tickets by text query, with optional status and site filters. Results are scoped to the caller's authorized scope.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search terms (plain text only, search operators are not permitted)"},
                "status": {"type": "string", "enum": ["open", "closed", "all"], "description": "Filter by ticket status"},
                "site": {"type": "string", "description": "Filter by site code"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "ticket_create",
        "description": "[WRITE] Open a new exception ticket for an operational problem.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "site": {"type": "string", "description": "Site code where the exception occurred", "enum": [f"SITE-{i:02d}" for i in range(1, 12)]},
                "category": {"type": "string", "description": "Ticket category", "enum": ["damaged_goods", "short_shipment", "late_arrival", "system_error", "other"]},
                "summary": {"type": "string", "description": "Brief summary (max 200 chars)", "maxLength": 200},
                "detail": {"type": "string", "description": "Detailed description (max 2000 chars)", "maxLength": 2000},
            },
            "required": ["site", "category", "summary", "detail"],
        },
    },
    {
        "name": "ticket_comment",
        "description": "[WRITE] Add a comment to an existing ticket. Note: comments on customer-facing tickets are visible to the customer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket identifier"},
                "body": {"type": "string", "description": "Comment text (max 2000 chars)", "maxLength": 2000},
            },
            "required": ["ticket_id", "body"],
        },
    },
    {
        "name": "ticket_close",
        "description": "[WRITE] Close a ticket with a resolution summary. Reopening is possible but audited. Requires human approval.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "string", "description": "Ticket identifier"},
                "resolution": {"type": "string", "description": "Resolution summary (max 500 chars)", "maxLength": 500},
            },
            "required": ["ticket_id", "resolution"],
        },
    },
    {
        "name": "contract_lookup",
        "description": "[READ] Look up a customer's contract terms including SLA details, service levels, and contacts. Scoped to the caller's authorized customers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer account identifier"},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "rate_card_lookup",
        "description": "[READ — COMMERCIALLY SENSITIVE] Look up a customer's negotiated rate card. Contains confidential pricing that must not be disclosed between customers. Restricted to Finance Analytics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "Customer account identifier"},
            },
            "required": ["customer_id"],
        },
    },
]


class KestrelGateway:
    def __init__(
        self,
        settings: GatewaySettings,
        kill_switch: KillSwitch | None = None,
        audit_logger: AuditLogger | None = None,
        rate_limiter: RateLimiter | None = None,
        sanitizer: Sanitizer | None = None,
        composition_guard: CompositionGuard | None = None,
        approval_gate: ApprovalGate | None = None,
        wms_client: WmsClient | None = None,
        tms_client: TmsClient | None = None,
        ticketing_client: TicketingClient | None = None,
        contracts_client: ContractsClient | None = None,
    ):
        self.settings = settings
        self.kill_switch = kill_switch or KillSwitch(settings.kill_switch_path)
        self.audit_logger = audit_logger or AuditLogger(settings.audit_log_path)
        self.rate_limiter = rate_limiter or RateLimiter()
        self.sanitizer = sanitizer or Sanitizer()
        self.composition_guard = composition_guard or CompositionGuard()
        self.approval_gate = approval_gate or ApprovalGate()

        self.wms = wms_client or WmsClient(settings.wms_base_url, settings.wms_api_key)
        self.tms = tms_client or TmsClient(settings.tms_base_url, settings.tms_client_id, settings.tms_client_secret)
        self.ticketing = ticketing_client or TicketingClient(settings.ticketing_base_url, settings.ticketing_bearer_token)
        self.contracts = contracts_client or ContractsClient(settings.contracts_base_url)

        self.server = Server("kestrel-gateway")
        self._caller: CallerIdentity | None = None
        self._register_tools()

    def set_caller(self, caller: CallerIdentity) -> None:
        self._caller = caller

    def _register_tools(self) -> None:
        tools = [Tool(**td) for td in TOOL_DEFINITIONS]
        gateway = self

        async def handle_list_tools(*args):
            return ListToolsResult(tools=tools)

        async def handle_call_tool(*args):
            params = args[-1] if args else None
            if params is None:
                return CallToolResult(
                    content=[TextContent(type="text", text='{"error":"no params"}')]
                )
            result = await gateway._handle_tool_call(params.name, params.arguments or {})
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(result, default=str))]
            )

        self.server.add_request_handler("tools/list", type(None), handle_list_tools)
        self.server.add_request_handler("tools/call", CallToolRequestParams, handle_call_tool)

    async def _handle_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        request_id = str(uuid.uuid4())
        start = time.time()
        caller = self._caller
        if caller is None:
            return {"error": "No caller identity set", "code": "NO_IDENTITY"}

        system = TOOL_TO_SYSTEM.get(tool_name, "unknown")

        # 1. Authorization check
        authz = authorize(caller, tool_name, arguments)
        if not authz.allowed:
            record = AuditRecord(
                request_id=request_id, team=caller.team.value, user_id=caller.user_id,
                tool=tool_name, arguments=arguments, authz_decision="DENY",
                authz_rule=authz.rule, upstream_system=system,
                duration_ms=(time.time() - start) * 1000,
            )
            await self.audit_logger.log(record)
            return authorization_error(tool_name, authz.reason or "Unauthorized").model_dump()

        # 2. Composition guard
        violation = self.composition_guard.check_pre_call(caller, tool_name, arguments)
        if violation:
            record = AuditRecord(
                request_id=request_id, team=caller.team.value, user_id=caller.user_id,
                tool=tool_name, arguments=arguments, authz_decision="DENY",
                authz_rule=f"composition:{violation.risk}",
                upstream_system=system,
                duration_ms=(time.time() - start) * 1000,
            )
            await self.audit_logger.log(record)
            return authorization_error(tool_name, violation.description).model_dump()

        # 3. Kill switch
        ks_reason = self.kill_switch.check(tool_name, caller.team.value)
        if ks_reason:
            record = AuditRecord(
                request_id=request_id, team=caller.team.value, user_id=caller.user_id,
                tool=tool_name, arguments=arguments, authz_decision="ALLOW",
                authz_rule=authz.rule, upstream_system=system,
                kill_switch_blocked=True,
                duration_ms=(time.time() - start) * 1000,
            )
            await self.audit_logger.log(record)
            return kill_switch_error(tool_name, ks_reason).model_dump()

        # 4. Rate limit
        if not self.rate_limiter.check(caller.team.value, system, tool_name):
            record = AuditRecord(
                request_id=request_id, team=caller.team.value, user_id=caller.user_id,
                tool=tool_name, arguments=arguments, authz_decision="ALLOW",
                authz_rule=authz.rule, upstream_system=system,
                rate_limit_blocked=True,
                duration_ms=(time.time() - start) * 1000,
            )
            await self.audit_logger.log(record)
            return rate_limit_error(tool_name, caller.team.value).model_dump()

        # 5. Approval gate for state-changing operations
        if tool_name in APPROVAL_REQUIRED:
            if not self.approval_gate.auto_approve:
                req = self.approval_gate.request_approval(
                    tool=tool_name, team=caller.team.value, user_id=caller.user_id,
                    arguments=arguments,
                    reason=f"Operation '{tool_name}' is irreversible or financially committing",
                )
                record = AuditRecord(
                    request_id=request_id, team=caller.team.value, user_id=caller.user_id,
                    tool=tool_name, arguments=arguments, authz_decision="ALLOW",
                    authz_rule=authz.rule, upstream_system=system,
                    approval_required=True, approval_decision="PENDING",
                    approval_id=req.approval_id,
                    duration_ms=(time.time() - start) * 1000,
                )
                await self.audit_logger.log(record)
                return approval_required_error(tool_name, req.approval_id).model_dump()

        # 6. Enforce scope on arguments
        arguments = enforce_scope(caller, tool_name, arguments)

        # 7. Sanitize inputs
        arguments = self._sanitize_arguments(tool_name, arguments)

        # 8. Call upstream
        try:
            status, data = await self._dispatch(tool_name, arguments)
        except Exception as exc:
            record = AuditRecord(
                request_id=request_id, team=caller.team.value, user_id=caller.user_id,
                tool=tool_name, arguments=arguments, authz_decision="ALLOW",
                authz_rule=authz.rule, upstream_system=system,
                error=str(exc),
                duration_ms=(time.time() - start) * 1000,
            )
            await self.audit_logger.log(record)
            return upstream_error(tool_name, 500, "Internal gateway error").model_dump()

        if status >= 400:
            record = AuditRecord(
                request_id=request_id, team=caller.team.value, user_id=caller.user_id,
                tool=tool_name, arguments=arguments, authz_decision="ALLOW",
                authz_rule=authz.rule, upstream_system=system,
                upstream_status=status, error=str(data),
                duration_ms=(time.time() - start) * 1000,
            )
            await self.audit_logger.log(record)
            msg = data.get("detail", "Upstream error") if isinstance(data, dict) else str(data)
            return upstream_error(tool_name, status, msg).model_dump()

        # 9. Sanitize output
        data = self.sanitizer.sanitize_upstream_response(data)

        # 10. Composition filtering on results
        data, was_filtered = self.composition_guard.filter_results(caller, tool_name, data)

        # 11. Wrap content boundary
        result = self.sanitizer.wrap_upstream_content(data)

        # 12. Audit log
        record = AuditRecord(
            request_id=request_id, team=caller.team.value, user_id=caller.user_id,
            tool=tool_name, arguments=arguments, authz_decision="ALLOW",
            authz_rule=authz.rule, upstream_system=system,
            upstream_status=status, result_filtered=was_filtered,
            approval_required=tool_name in APPROVAL_REQUIRED,
            approval_decision="AUTO_APPROVED" if tool_name in APPROVAL_REQUIRED else None,
            duration_ms=(time.time() - start) * 1000,
        )
        await self.audit_logger.log(record)

        return {"success": True, **result}

    def _sanitize_arguments(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        args = dict(arguments)
        if tool_name in ("ticket_search",) and "query" in args:
            args["query"] = self.sanitizer.sanitize_search_query(args["query"])
        if tool_name in ("ticket_create",):
            if "detail" in args:
                args["detail"] = self.sanitizer.sanitize_text_input(args["detail"])
            if "summary" in args:
                args["summary"] = self.sanitizer.sanitize_text_input(args["summary"])
        if tool_name in ("ticket_comment",) and "body" in args:
            args["body"] = self.sanitizer.sanitize_text_input(args["body"])
        return args

    async def _dispatch(self, tool_name: str, arguments: dict[str, Any]) -> tuple[int, Any]:
        if tool_name == "wms_stock_lookup":
            return await self.wms.stock_lookup(arguments["sku"], arguments["site"])
        elif tool_name == "tms_dock_schedule":
            return await self.tms.dock_schedule(arguments["site"], arguments["date_from"], arguments["date_to"])
        elif tool_name == "tms_booking_lookup":
            return await self.tms.booking_lookup(arguments["booking_ref"])
        elif tool_name == "tms_booking_create":
            return await self.tms.booking_create(
                arguments["site"], arguments["carrier"], arguments["window"], arguments["load_ref"],
            )
        elif tool_name == "tms_booking_cancel":
            return await self.tms.booking_cancel(arguments["booking_ref"], arguments["reason"])
        elif tool_name == "ticket_search":
            return await self.ticketing.search(
                arguments["query"], arguments.get("status"), arguments.get("site"),
            )
        elif tool_name == "ticket_create":
            return await self.ticketing.create(
                arguments["site"], arguments["category"], arguments["summary"], arguments["detail"],
            )
        elif tool_name == "ticket_comment":
            return await self.ticketing.comment(arguments["ticket_id"], arguments["body"])
        elif tool_name == "ticket_close":
            return await self.ticketing.close(arguments["ticket_id"], arguments["resolution"])
        elif tool_name == "contract_lookup":
            return await self.contracts.contract_lookup(arguments["customer_id"])
        elif tool_name == "rate_card_lookup":
            return await self.contracts.rate_card_lookup(arguments["customer_id"])
        else:
            return 400, {"detail": f"Unknown tool: {tool_name}"}
