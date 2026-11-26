"""
SYS-1  WMS Stub  (FastAPI, port 8081)

Endpoints
---------
GET  /stock/{sku}?site={site}   — look up stock for a SKU at a site
POST /stock/adjust              — adjust quantity (add / remove)
POST /bin/move                  — move stock between bins

Auth : X-API-Key header (expected value: test-wms-key)
Limit: 600 req/min (in-memory counter, resets every 60 s)
"""

from __future__ import annotations

import copy
import time
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

# -- seed data ---------------------------------------------------------------
from stubs.data.seed_data import WMS_STOCK

app = FastAPI(title="WMS Stub", version="0.1.0")

# In-memory store — deep-copy so we don't mutate the seed module
_stock: list[dict] = copy.deepcopy(WMS_STOCK)

# ---------------------------------------------------------------------------
# Rate limiter (600 req/min, simple sliding-window counter)
# ---------------------------------------------------------------------------
_RATE_LIMIT = 600
_WINDOW_SEC = 60
_request_log: list[float] = []


def _check_rate_limit() -> None:
    now = time.monotonic()
    # Prune old entries
    while _request_log and _request_log[0] < now - _WINDOW_SEC:
        _request_log.pop(0)
    if len(_request_log) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded (600 req/min)")
    _request_log.append(now)


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------
_EXPECTED_KEY = "test-wms-key"


def _check_auth(api_key: str | None) -> None:
    if api_key != _EXPECTED_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class StockAdjust(BaseModel):
    sku: str
    site: str
    quantity_delta: int  # positive = add, negative = remove
    reason: str = ""


class BinMove(BaseModel):
    sku: str
    site: str
    from_bin: str
    to_bin: str
    quantity: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/stock/{sku}")
def get_stock(
    sku: str,
    site: Optional[str] = Query(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    _check_auth(x_api_key)
    _check_rate_limit()

    matches = [r for r in _stock if r["sku"] == sku and (site is None or r["site"] == site)]
    if not matches:
        raise HTTPException(status_code=404, detail=f"No stock found for SKU {sku}" + (f" at {site}" if site else ""))
    # If site was given there is at most one logical record, but return a list
    # for consistency with multi-site queries.
    return {"results": matches}


@app.post("/stock/adjust")
def adjust_stock(
    body: StockAdjust,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    _check_auth(x_api_key)
    _check_rate_limit()

    for rec in _stock:
        if rec["sku"] == body.sku and rec["site"] == body.site:
            new_qty = rec["quantity"] + body.quantity_delta
            if new_qty < 0:
                raise HTTPException(status_code=400, detail="Adjustment would result in negative stock")
            rec["quantity"] = new_qty
            return {"status": "adjusted", "sku": body.sku, "site": body.site, "new_quantity": new_qty}
    raise HTTPException(status_code=404, detail=f"No stock record for {body.sku} at {body.site}")


@app.post("/bin/move")
def bin_move(
    body: BinMove,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
):
    _check_auth(x_api_key)
    _check_rate_limit()

    source = None
    for rec in _stock:
        if rec["sku"] == body.sku and rec["site"] == body.site and rec["bin"] == body.from_bin:
            source = rec
            break

    if source is None:
        raise HTTPException(status_code=404, detail="Source bin/SKU/site combination not found")
    if source["quantity"] < body.quantity:
        raise HTTPException(status_code=400, detail="Insufficient quantity in source bin")

    # Deduct from source
    source["quantity"] -= body.quantity

    # Add to target (create record if needed)
    target = None
    for rec in _stock:
        if rec["sku"] == body.sku and rec["site"] == body.site and rec["bin"] == body.to_bin:
            target = rec
            break
    if target is None:
        target = {
            "sku": body.sku,
            "site": body.site,
            "quantity": 0,
            "bin": body.to_bin,
            "last_count_date": source["last_count_date"],
        }
        _stock.append(target)
    target["quantity"] += body.quantity

    return {
        "status": "moved",
        "sku": body.sku,
        "site": body.site,
        "from_bin": body.from_bin,
        "to_bin": body.to_bin,
        "quantity_moved": body.quantity,
    }


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)
