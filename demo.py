"""Full gateway demo — runs in-process with ASGI stubs, no Docker needed."""

import asyncio
import json
import os
import tempfile

import httpx
from httpx import ASGITransport

from stubs.wms_stub import app as wms_app
from stubs.tms_stub import app as tms_app
from stubs.ticketing_stub import app as ticketing_app
from stubs.contracts_stub import app as contracts_app
from stubs.data.seed_data import WMS_STOCK, TMS_BOOKINGS, TICKETS, CONTRACTS, RATE_CARDS

from kestrel_gateway.server import KestrelGateway
from kestrel_gateway.config.settings import GatewaySettings
from kestrel_gateway.config.teams import Team
from kestrel_gateway.auth.context import CallerIdentity
from kestrel_gateway.clients.wms_client import WmsClient
from kestrel_gateway.clients.tms_client import TmsClient
from kestrel_gateway.clients.ticketing_client import TicketingClient
from kestrel_gateway.clients.contracts_client import ContractsClient


def _make_client(cls, app, headers=None, **extra):
    transport = ASGITransport(app=app)
    http = httpx.AsyncClient(transport=transport, base_url="http://test")
    obj = cls.__new__(cls)
    obj._base_url = "http://test"
    obj._timeout = 10.0
    obj._client = http
    if headers:
        obj._headers = headers
    for k, v in extra.items():
        setattr(obj, k, v)
    return obj, http


async def main():
    print("=" * 60)
    print("  KESTREL MCP GATEWAY — LIVE DEMO")
    print("=" * 60)
    print()

    # Seed data summary
    print("SEED DATA LOADED")
    print(f"  WMS stock records : {len(WMS_STOCK)}")
    print(f"  TMS bookings      : {len(TMS_BOOKINGS)}")
    print(f"  Tickets           : {len(TICKETS)}")
    print(f"  Contracts         : {len(CONTRACTS)}")
    print(f"  Rate cards        : {len(RATE_CARDS)}")
    print()

    print("RATE CARD DIFFERENTIATION (commercially sensitive)")
    for rc in RATE_CARDS:
        r = rc["rates"][0]
        print(f"  {rc['customer_id']}: GBP {r['rate_gbp']}/{r['unit']}")
    print()

    # Build in-process clients
    wms_client, wms_http = _make_client(
        WmsClient, wms_app, headers={"X-API-Key": "test-wms-key"},
    )
    tms_client, tms_http = _make_client(
        TmsClient, tms_app,
        _client_id="tms-client", _client_secret="tms-secret",
        _access_token=None, _token_expiry=0,
    )
    ticket_client, ticket_http = _make_client(
        TicketingClient, ticketing_app,
        headers={"Authorization": "Bearer test-ticket-token"},
    )
    contract_client, contract_http = _make_client(
        ContractsClient, contracts_app,
        headers={"X-Client-Cert": "valid"},
    )

    tmp = tempfile.mkdtemp()
    settings = GatewaySettings(
        WMS_API_KEY="test-wms-key",
        TMS_CLIENT_ID="tms-client",
        TMS_CLIENT_SECRET="tms-secret",
        TICKETING_BEARER_TOKEN="test-ticket-token",
        kill_switch_path=os.path.join(tmp, "ks.json"),
        audit_log_path=os.path.join(tmp, "audit.jsonl"),
    )

    gw = KestrelGateway(
        settings=settings,
        wms_client=wms_client,
        tms_client=tms_client,
        ticketing_client=ticket_client,
        contracts_client=contract_client,
    )
    gw.approval_gate.set_auto_approve(True)

    def pp(result):
        return json.dumps(result, indent=2, default=str)

    # ----------------------------------------------------------------
    print("-" * 60)
    print("DEMO 1: Warehouse Ops @ SITE-01 — stock lookup (ALLOWED)")
    print("-" * 60)
    caller = CallerIdentity(team=Team.WAREHOUSE_OPS, user_id="wh-alice", site="SITE-01")
    gw.set_caller(caller)
    r = await gw._handle_tool_call("wms_stock_lookup", {"sku": "SKU-001", "site": "SITE-01"})
    print(pp(r))
    print()

    # ----------------------------------------------------------------
    print("-" * 60)
    print("DEMO 2: Warehouse Ops @ SITE-01 — cross-site attempt (BLOCKED)")
    print("-" * 60)
    r = await gw._handle_tool_call("wms_stock_lookup", {"sku": "SKU-001", "site": "SITE-02"})
    print(pp(r))
    print()

    # ----------------------------------------------------------------
    print("-" * 60)
    print("DEMO 3: Customer Service for CUST-A — contract lookup (ALLOWED)")
    print("-" * 60)
    caller = CallerIdentity(team=Team.CUSTOMER_SERVICE, user_id="cs-bob", customer_ids=["CUST-A"])
    gw.set_caller(caller)
    r = await gw._handle_tool_call("contract_lookup", {"customer_id": "CUST-A"})
    print(pp(r))
    print()

    # ----------------------------------------------------------------
    print("-" * 60)
    print("DEMO 4: Customer Service for CUST-A — cross-customer attempt (BLOCKED)")
    print("-" * 60)
    r = await gw._handle_tool_call("contract_lookup", {"customer_id": "CUST-B"})
    print(pp(r))
    print()

    # ----------------------------------------------------------------
    print("-" * 60)
    print("DEMO 5: Customer Service — rate_card_lookup (ACL BLOCKED)")
    print("-" * 60)
    r = await gw._handle_tool_call("rate_card_lookup", {"customer_id": "CUST-A"})
    print(pp(r))
    print()

    # ----------------------------------------------------------------
    print("-" * 60)
    print("DEMO 6: Finance Analytics — rate_card_lookup (ALLOWED)")
    print("-" * 60)
    caller = CallerIdentity(team=Team.FINANCE_ANALYTICS, user_id="fin-carol")
    gw.set_caller(caller)
    r = await gw._handle_tool_call("rate_card_lookup", {"customer_id": "CUST-A"})
    print(pp(r))
    print()

    # ----------------------------------------------------------------
    print("-" * 60)
    print("DEMO 7: ticket_delete — NOT EXPOSED (blocked for all teams)")
    print("-" * 60)
    r = await gw._handle_tool_call("ticket_delete", {"ticket_id": "TKT-001"})
    print(pp(r))
    print()

    # ----------------------------------------------------------------
    print("-" * 60)
    print("DEMO 8: Kill switch — disable and re-enable a tool at runtime")
    print("-" * 60)
    caller = CallerIdentity(team=Team.WAREHOUSE_OPS, user_id="wh-alice", site="SITE-01")
    gw.set_caller(caller)
    gw.kill_switch.disable_tool("wms_stock_lookup")
    r = await gw._handle_tool_call("wms_stock_lookup", {"sku": "SKU-001", "site": "SITE-01"})
    print("  Tool DISABLED:")
    print(f"  {pp(r)}")
    gw.kill_switch.enable_tool("wms_stock_lookup")
    r = await gw._handle_tool_call("wms_stock_lookup", {"sku": "SKU-001", "site": "SITE-01"})
    print(f"  Tool RE-ENABLED: success={r.get('success')}")
    print()

    # ----------------------------------------------------------------
    print("-" * 60)
    print("DEMO 9: Approval gate — booking_create requires human approval")
    print("-" * 60)
    gw.approval_gate.set_auto_approve(False)
    caller = CallerIdentity(team=Team.TRANSPORT_PLANNING, user_id="tp-dave")
    gw.set_caller(caller)
    r = await gw._handle_tool_call("tms_booking_create", {
        "site": "SITE-01", "carrier": "DHL",
        "window": "2026-04-20T08:00:00", "load_ref": "LD-999",
    })
    print(pp(r))
    print()

    # ----------------------------------------------------------------
    print("-" * 60)
    print("DEMO 10: Input sanitization — search with operators stripped")
    print("-" * 60)
    gw.approval_gate.set_auto_approve(True)
    caller = CallerIdentity(team=Team.WAREHOUSE_OPS, user_id="wh-alice", site="SITE-01")
    gw.set_caller(caller)
    r = await gw._handle_tool_call("ticket_search", {
        "query": "damaged OR status:closed NOT site:*",
        "status": "open", "site": "SITE-01",
    })
    print(f"  Original query: 'damaged OR status:closed NOT site:*'")
    print(f"  (Operators stripped by gateway before forwarding to upstream)")
    print(f"  Result success: {r.get('success')}")
    print()

    # ----------------------------------------------------------------
    print("=" * 60)
    print("AUDIT LOG")
    print("=" * 60)
    records = await gw.audit_logger.get_records()
    print(f"  {len(records)} audit records captured:\n")
    for rec in records:
        marker = "ALLOW" if rec.authz_decision == "ALLOW" else "DENY "
        extra = ""
        if rec.kill_switch_blocked:
            extra = " [KILL SWITCH]"
        elif rec.rate_limit_blocked:
            extra = " [RATE LIMITED]"
        elif rec.approval_required and rec.approval_decision == "PENDING":
            extra = " [APPROVAL PENDING]"
        print(f"  [{marker}] {rec.team:20s} / {rec.user_id:10s} -> {rec.tool:25s}{extra}")
        print(f"          rule: {rec.authz_rule[:70]}")

    # Cleanup
    await wms_http.aclose()
    await tms_http.aclose()
    await ticket_http.aclose()
    await contract_http.aclose()


if __name__ == "__main__":
    asyncio.run(main())
