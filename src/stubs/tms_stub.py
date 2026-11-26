"""
SYS-2  TMS Stub  (FastAPI, port 8082)

Endpoints
---------
POST /oauth/token                              — issue an access token
GET  /dock-schedule?site=&from=&to=            — dock schedule for a site/date range
GET  /booking/{ref}                            — look up a single booking
POST /booking                                  — create a booking
POST /booking/{ref}/cancel                     — cancel a booking

Auth : OAuth2 — POST /oauth/token to get a Bearer token
Limit: 120 req/min per token
"""

from __future__ import annotations

import copy
import secrets
import time
import uuid
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from stubs.data.seed_data import TMS_BOOKINGS, TMS_DOCK_SCHEDULE

app = FastAPI(title="TMS Stub", version="0.1.0")

# In-memory stores
_bookings: list[dict] = copy.deepcopy(TMS_BOOKINGS)
_dock_schedule: list[dict] = copy.deepcopy(TMS_DOCK_SCHEDULE)

# ---------------------------------------------------------------------------
# OAuth token store  { token_string: {"client_id": ..., "issued": monotonic} }
# ---------------------------------------------------------------------------
_VALID_CLIENTS = {
    "tms-client": "tms-secret",
}
_tokens: dict[str, dict] = {}

# ---------------------------------------------------------------------------
# Per-token rate limiter (120 req/min)
# ---------------------------------------------------------------------------
_RATE_LIMIT = 120
_WINDOW_SEC = 60
_token_requests: dict[str, list[float]] = {}  # token -> list of timestamps


def _check_rate_limit(token: str) -> None:
    now = time.monotonic()
    log = _token_requests.setdefault(token, [])
    while log and log[0] < now - _WINDOW_SEC:
        log.pop(0)
    if len(log) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded (120 req/min)")
    log.append(now)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
class TokenRequest(BaseModel):
    client_id: str
    client_secret: str
    grant_type: str = "client_credentials"


def _validate_bearer(authorization: str | None) -> str:
    """Return the token string or raise 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[7:]
    if token not in _tokens:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return token


# ---------------------------------------------------------------------------
# Endpoints — OAuth
# ---------------------------------------------------------------------------
@app.post("/oauth/token")
def issue_token(body: TokenRequest):
    expected_secret = _VALID_CLIENTS.get(body.client_id)
    if expected_secret is None or expected_secret != body.client_secret:
        raise HTTPException(status_code=401, detail="Invalid client credentials")
    token = secrets.token_hex(32)
    _tokens[token] = {"client_id": body.client_id, "issued": time.monotonic()}
    return {"access_token": token, "token_type": "bearer", "expires_in": 3600}


# ---------------------------------------------------------------------------
# Endpoints — dock schedule
# ---------------------------------------------------------------------------
@app.get("/dock-schedule")
def dock_schedule(
    site: str = Query(...),
    from_date: str = Query(..., alias="from"),
    to_date: str = Query(..., alias="to"),
    authorization: Optional[str] = Header(None),
):
    token = _validate_bearer(authorization)
    _check_rate_limit(token)

    results = [
        d for d in _dock_schedule
        if d["site"] == site and from_date <= d["date"] <= to_date
    ]
    return {"results": results}


# ---------------------------------------------------------------------------
# Endpoints — bookings
# ---------------------------------------------------------------------------
@app.get("/booking/{ref}")
def get_booking(
    ref: str,
    authorization: Optional[str] = Header(None),
):
    token = _validate_bearer(authorization)
    _check_rate_limit(token)

    for b in _bookings:
        if b["booking_ref"] == ref:
            return b
    raise HTTPException(status_code=404, detail=f"Booking {ref} not found")


class BookingCreate(BaseModel):
    site: str
    carrier: str
    vehicle: str
    window: dict  # {"from": ..., "to": ...}
    load_ref: str


@app.post("/booking", status_code=201)
def create_booking(
    body: BookingCreate,
    authorization: Optional[str] = Header(None),
):
    token = _validate_bearer(authorization)
    _check_rate_limit(token)

    ref = f"BK-{uuid.uuid4().hex[:6].upper()}"
    new_booking = {
        "booking_ref": ref,
        "site": body.site,
        "carrier": body.carrier,
        "vehicle": body.vehicle,
        "window": body.window,
        "load_ref": body.load_ref,
        "status": "pending",
    }
    _bookings.append(new_booking)
    return {"booking_ref": ref, "status": "pending"}


@app.post("/booking/{ref}/cancel")
def cancel_booking(
    ref: str,
    authorization: Optional[str] = Header(None),
):
    token = _validate_bearer(authorization)
    _check_rate_limit(token)

    for b in _bookings:
        if b["booking_ref"] == ref:
            if b["status"] == "cancelled":
                raise HTTPException(status_code=409, detail="Booking already cancelled")
            b["status"] = "cancelled"
            return {"booking_ref": ref, "status": "cancelled"}
    raise HTTPException(status_code=404, detail=f"Booking {ref} not found")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8082)
