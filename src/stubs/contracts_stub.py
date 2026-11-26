"""
SYS-4  Contracts Stub  (FastAPI, port 8084)

Endpoints
---------
GET /contract/{customer_id}         — single customer's contract
GET /rate-card/{customer_id}        — single customer's rate card
GET /contracts/search?text={text}   — search ALL contracts (unscoped!)

Auth : X-Client-Cert: valid  (simulates mTLS; no real cert in stubs)
Limit: 60 req/min

IMPORTANT: /contracts/search is *deliberately unscoped* — it returns
matches from any customer.  The gateway must refuse to expose this
endpoint (or scope it) to prevent cross-customer rate disclosure.
"""

from __future__ import annotations

import copy
import json
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query

from stubs.data.seed_data import CONTRACTS, RATE_CARDS

app = FastAPI(title="Contracts Stub", version="0.1.0")

# In-memory stores
_contracts: list[dict] = copy.deepcopy(CONTRACTS)
_rate_cards: list[dict] = copy.deepcopy(RATE_CARDS)

# ---------------------------------------------------------------------------
# Rate limiter (60 req/min)
# ---------------------------------------------------------------------------
_RATE_LIMIT = 60
_WINDOW_SEC = 60
_request_log: list[float] = []


def _check_rate_limit() -> None:
    now = time.monotonic()
    while _request_log and _request_log[0] < now - _WINDOW_SEC:
        _request_log.pop(0)
    if len(_request_log) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded (60 req/min)")
    _request_log.append(now)


# ---------------------------------------------------------------------------
# Auth — simulated mTLS via X-Client-Cert header
# ---------------------------------------------------------------------------
def _check_auth(client_cert: str | None) -> None:
    if client_cert != "valid":
        raise HTTPException(status_code=403, detail="Missing or invalid client certificate")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/contract/{customer_id}")
def get_contract(
    customer_id: str,
    x_client_cert: Optional[str] = Header(None, alias="X-Client-Cert"),
):
    _check_auth(x_client_cert)
    _check_rate_limit()

    for c in _contracts:
        if c["customer_id"] == customer_id:
            return c
    raise HTTPException(status_code=404, detail=f"Contract for {customer_id} not found")


@app.get("/rate-card/{customer_id}")
def get_rate_card(
    customer_id: str,
    x_client_cert: Optional[str] = Header(None, alias="X-Client-Cert"),
):
    _check_auth(x_client_cert)
    _check_rate_limit()

    for r in _rate_cards:
        if r["customer_id"] == customer_id:
            return r
    raise HTTPException(status_code=404, detail=f"Rate card for {customer_id} not found")


@app.get("/contracts/search")
def contract_search(
    text: str = Query(...),
    x_client_cert: Optional[str] = Header(None, alias="X-Client-Cert"),
):
    """
    Deliberately unscoped search — returns matches from ANY customer.
    The gateway must refuse to expose this or add scoping.
    """
    _check_auth(x_client_cert)
    _check_rate_limit()

    t_lower = text.lower()
    results: list[dict] = []

    for c in _contracts:
        blob = json.dumps(c).lower()
        if t_lower in blob:
            results.append(c)

    # Also search rate cards
    rate_hits: list[dict] = []
    for r in _rate_cards:
        blob = json.dumps(r).lower()
        if t_lower in blob:
            rate_hits.append(r)

    return {"contracts": results, "rate_cards": rate_hits, "total": len(results) + len(rate_hits)}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8084)
