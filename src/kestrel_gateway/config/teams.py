from __future__ import annotations

from enum import Enum
from typing import Optional


class Team(str, Enum):
    WAREHOUSE_OPS = "warehouse_ops"
    TRANSPORT_PLANNING = "transport_planning"
    CUSTOMER_SERVICE = "customer_service"
    FINANCE_ANALYTICS = "finance_analytics"


class Site(str, Enum):
    SITE_01 = "SITE-01"
    SITE_02 = "SITE-02"
    SITE_03 = "SITE-03"
    SITE_04 = "SITE-04"
    SITE_05 = "SITE-05"
    SITE_06 = "SITE-06"
    SITE_07 = "SITE-07"
    SITE_08 = "SITE-08"
    SITE_09 = "SITE-09"
    SITE_10 = "SITE-10"
    SITE_11 = "SITE-11"


TOOL_ACL: dict[str, set[Team]] = {
    "wms_stock_lookup": {Team.WAREHOUSE_OPS, Team.TRANSPORT_PLANNING, Team.CUSTOMER_SERVICE, Team.FINANCE_ANALYTICS},
    "tms_dock_schedule": {Team.TRANSPORT_PLANNING, Team.FINANCE_ANALYTICS},
    "tms_booking_lookup": {Team.TRANSPORT_PLANNING, Team.FINANCE_ANALYTICS},
    "tms_booking_create": {Team.TRANSPORT_PLANNING},
    "tms_booking_cancel": {Team.TRANSPORT_PLANNING},
    "ticket_search": {Team.WAREHOUSE_OPS, Team.TRANSPORT_PLANNING, Team.CUSTOMER_SERVICE},
    "ticket_create": {Team.WAREHOUSE_OPS, Team.TRANSPORT_PLANNING, Team.CUSTOMER_SERVICE},
    "ticket_comment": {Team.WAREHOUSE_OPS, Team.CUSTOMER_SERVICE},
    "ticket_close": {Team.CUSTOMER_SERVICE},
    "contract_lookup": {Team.CUSTOMER_SERVICE, Team.FINANCE_ANALYTICS},
    "rate_card_lookup": {Team.FINANCE_ANALYTICS},
    # ticket_delete: NEVER exposed — hard delete, not recoverable
    # contract_search: NEVER exposed — unscoped free-text across all contracts
    # wms_stock_adjust: not exposed — no team requests SYS-1 write
    # wms_bin_move: not exposed — no team requests SYS-1 write
}

APPROVAL_REQUIRED: set[str] = {
    "tms_booking_create",
    "tms_booking_cancel",
    "ticket_close",
}

ROW_SCOPE_FIELD: dict[Team, Optional[str]] = {
    Team.WAREHOUSE_OPS: "site",
    Team.TRANSPORT_PLANNING: None,
    Team.CUSTOMER_SERVICE: "customer_id",
    Team.FINANCE_ANALYTICS: None,
}

# Per-team rate limits per system (requests per minute)
RATE_LIMITS: dict[str, dict[Team, int]] = {
    "wms": {
        Team.WAREHOUSE_OPS: 150,
        Team.TRANSPORT_PLANNING: 150,
        Team.CUSTOMER_SERVICE: 150,
        Team.FINANCE_ANALYTICS: 150,
    },
    "tms": {
        Team.TRANSPORT_PLANNING: 60,
        Team.FINANCE_ANALYTICS: 60,
    },
    "ticketing": {
        Team.WAREHOUSE_OPS: 100,
        Team.TRANSPORT_PLANNING: 100,
        Team.CUSTOMER_SERVICE: 100,
    },
    "contracts": {
        Team.CUSTOMER_SERVICE: 20,
        Team.FINANCE_ANALYTICS: 20,
    },
}

RATE_CARD_LOOKUP_LIMIT: dict[Team, int] = {
    Team.FINANCE_ANALYTICS: 10,
}

TOOL_TO_SYSTEM: dict[str, str] = {
    "wms_stock_lookup": "wms",
    "tms_dock_schedule": "tms",
    "tms_booking_lookup": "tms",
    "tms_booking_create": "tms",
    "tms_booking_cancel": "tms",
    "ticket_search": "ticketing",
    "ticket_create": "ticketing",
    "ticket_comment": "ticketing",
    "ticket_close": "ticketing",
    "contract_lookup": "contracts",
    "rate_card_lookup": "contracts",
}
