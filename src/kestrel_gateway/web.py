"""HTTP entry point for Render / cloud deployment.

Starts the gateway as an HTTP service with Streamable HTTP transport,
plus runs the 4 upstream stubs in-process for the demo deployment.
"""

import os
import threading
import uvicorn
from starlette.applications import Starlette

from kestrel_gateway.auth.context import CallerIdentity
from kestrel_gateway.config.settings import load_settings
from kestrel_gateway.config.teams import Team
from kestrel_gateway.server import KestrelGateway

# Default callers for demo — keyed by team name
DEFAULT_CALLERS = {
    "warehouse_ops": CallerIdentity(team=Team.WAREHOUSE_OPS, user_id="demo-wh-user", site="SITE-01"),
    "transport_planning": CallerIdentity(team=Team.TRANSPORT_PLANNING, user_id="demo-tp-user"),
    "customer_service": CallerIdentity(team=Team.CUSTOMER_SERVICE, user_id="demo-cs-user", customer_ids=["CUST-A"]),
    "finance_analytics": CallerIdentity(team=Team.FINANCE_ANALYTICS, user_id="demo-fin-user"),
}


def create_app() -> Starlette:
    settings = load_settings()
    gateway = KestrelGateway(settings)

    # Set default caller from env, or Finance Analytics (broadest read access)
    default_team = os.environ.get("DEFAULT_TEAM", "finance_analytics")
    caller = DEFAULT_CALLERS.get(default_team, DEFAULT_CALLERS["finance_analytics"])
    gateway.set_caller(caller)
    gateway.approval_gate.set_auto_approve(True)

    return gateway.server.streamable_http_app(host="0.0.0.0")


def start_stubs():
    """Run all 4 stubs in background threads (for demo/free-tier deployment)."""
    from stubs.wms_stub import app as wms_app
    from stubs.tms_stub import app as tms_app
    from stubs.ticketing_stub import app as ticketing_app
    from stubs.contracts_stub import app as contracts_app

    stubs = [
        (wms_app, 8081),
        (tms_app, 8082),
        (ticketing_app, 8083),
        (contracts_app, 8084),
    ]
    for app, port in stubs:
        t = threading.Thread(
            target=uvicorn.run,
            args=(app,),
            kwargs={"host": "127.0.0.1", "port": port, "log_level": "warning"},
            daemon=True,
        )
        t.start()


app = create_app()

if os.environ.get("RUN_STUBS", "true").lower() == "true":
    start_stubs()
