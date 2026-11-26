"""
Shared fixtures for the Kestrel MCP Gateway test suite.

All upstream systems run as in-process FastAPI stubs via httpx.ASGITransport,
so no network is involved.  The gateway is tested through its internal
``_handle_tool_call`` method.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport

from stubs.wms_stub import app as wms_app
from stubs.tms_stub import app as tms_app
from stubs.ticketing_stub import app as ticketing_app
from stubs.contracts_stub import app as contracts_app
import stubs.contracts_stub as _contracts_stub_mod
import stubs.wms_stub as _wms_stub_mod

from kestrel_gateway.server import KestrelGateway
from kestrel_gateway.config.settings import GatewaySettings
from kestrel_gateway.config.teams import Team
from kestrel_gateway.auth.context import CallerIdentity
from kestrel_gateway.clients.wms_client import WmsClient
from kestrel_gateway.clients.tms_client import TmsClient
from kestrel_gateway.clients.ticketing_client import TicketingClient
from kestrel_gateway.clients.contracts_client import ContractsClient


# ---------------------------------------------------------------------------
# In-process client fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def wms_client():
    transport = ASGITransport(app=wms_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        c = WmsClient.__new__(WmsClient)
        c._base_url = "http://test"
        c._timeout = 10.0
        c._client = client
        c._headers = {"X-API-Key": "test-wms-key"}
        yield c


@pytest_asyncio.fixture
async def tms_client():
    transport = ASGITransport(app=tms_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        c = TmsClient.__new__(TmsClient)
        c._base_url = "http://test"
        c._timeout = 10.0
        c._client = client
        c._client_id = "tms-client"
        c._client_secret = "tms-secret"
        c._access_token = None
        c._token_expiry = 0
        yield c


@pytest_asyncio.fixture
async def ticketing_client():
    transport = ASGITransport(app=ticketing_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        c = TicketingClient.__new__(TicketingClient)
        c._base_url = "http://test"
        c._timeout = 10.0
        c._client = client
        c._headers = {"Authorization": "Bearer test-ticket-token"}
        yield c


@pytest_asyncio.fixture
async def contracts_client():
    transport = ASGITransport(app=contracts_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        c = ContractsClient.__new__(ContractsClient)
        c._base_url = "http://test"
        c._timeout = 10.0
        c._client = client
        c._headers = {"X-Client-Cert": "valid"}
        yield c


# ---------------------------------------------------------------------------
# Gateway fixture
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def gateway(wms_client, tms_client, ticketing_client, contracts_client, tmp_path):
    settings = GatewaySettings(
        WMS_API_KEY="test-wms-key",
        TMS_CLIENT_ID="tms-client",
        TMS_CLIENT_SECRET="tms-secret",
        TICKETING_BEARER_TOKEN="test-ticket-token",
        wms_base_url="http://test",
        tms_base_url="http://test",
        ticketing_base_url="http://test",
        contracts_base_url="http://test",
        kill_switch_path=str(tmp_path / "kill_switch.json"),
        audit_log_path=str(tmp_path / "audit.jsonl"),
    )
    # Bypass MCP protocol registration -- we test _handle_tool_call directly
    with patch.object(KestrelGateway, "_register_tools", lambda self: None):
        gw = KestrelGateway(
            settings=settings,
            wms_client=wms_client,
            tms_client=tms_client,
            ticketing_client=ticketing_client,
            contracts_client=contracts_client,
        )
    gw.approval_gate.set_auto_approve(True)
    # Reset upstream stub rate limiters so test ordering does not matter
    _contracts_stub_mod._request_log.clear()
    _wms_stub_mod._request_log.clear()
    yield gw


# ---------------------------------------------------------------------------
# Caller identity fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def warehouse_ops_site_01():
    return CallerIdentity(team=Team.WAREHOUSE_OPS, user_id="wh-user-01", site="SITE-01")


@pytest.fixture
def warehouse_ops_site_02():
    return CallerIdentity(team=Team.WAREHOUSE_OPS, user_id="wh-user-02", site="SITE-02")


@pytest.fixture
def transport_planning():
    return CallerIdentity(team=Team.TRANSPORT_PLANNING, user_id="tp-user-01")


@pytest.fixture
def customer_service_cust_a():
    return CallerIdentity(team=Team.CUSTOMER_SERVICE, user_id="cs-user-01", customer_ids=["CUST-A"])


@pytest.fixture
def customer_service_cust_b():
    return CallerIdentity(team=Team.CUSTOMER_SERVICE, user_id="cs-user-02", customer_ids=["CUST-B"])


@pytest.fixture
def finance_analytics():
    return CallerIdentity(team=Team.FINANCE_ANALYTICS, user_id="fin-user-01")
