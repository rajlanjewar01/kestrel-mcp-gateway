"""
SYS-3  Ticketing Stub  (FastAPI, port 8083)

Endpoints
---------
GET    /tickets/search?query=&status=&site=   — search tickets (substring match)
POST   /tickets                                — create a ticket
POST   /tickets/{id}/comment                   — add comment to a ticket
POST   /tickets/{id}/close                     — close a ticket
DELETE /tickets/{id}                           — permanently delete a ticket

Auth : Bearer token (expected: test-ticket-token)
Limit: NONE — deliberately omitted so the gateway must impose its own

IMPORTANT: The search endpoint is *deliberately permissive* — it does a
plain substring match on summary+detail without filtering operators from
the query string.  This reproduces the real-world "permissive about
operators" behaviour that the gateway must protect against.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from stubs.data.seed_data import TICKETS

app = FastAPI(title="Ticketing Stub", version="0.1.0")

# In-memory store
_tickets: list[dict] = copy.deepcopy(TICKETS)
_comments: dict[str, list[dict]] = {}  # ticket_id -> [comment, ...]

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
_EXPECTED_TOKEN = "test-ticket-token"


def _check_auth(authorization: str | None) -> None:
    if not authorization or authorization != f"Bearer {_EXPECTED_TOKEN}":
        raise HTTPException(status_code=401, detail="Invalid or missing Bearer token")


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class TicketCreate(BaseModel):
    site: str
    customer_id: str
    category: str = "general"
    summary: str
    detail: str = ""
    created_by: str = "api"


class CommentAdd(BaseModel):
    author: str
    text: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/tickets/search")
def search_tickets(
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    site: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Deliberately permissive search — no operator filtering."""
    _check_auth(authorization)

    results = list(_tickets)  # start with everything

    if site:
        results = [t for t in results if t["site"] == site]

    if status:
        results = [t for t in results if t["status"] == status]

    if query:
        # Simple substring match on summary + detail — intentionally no
        # sanitisation of the query string.
        q_lower = query.lower()
        results = [
            t for t in results
            if q_lower in t["summary"].lower() or q_lower in t["detail"].lower()
        ]

    return {"results": results, "total": len(results)}


@app.post("/tickets", status_code=201)
def create_ticket(
    body: TicketCreate,
    authorization: Optional[str] = Header(None),
):
    _check_auth(authorization)

    ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
    ticket = {
        "ticket_id": ticket_id,
        "site": body.site,
        "customer_id": body.customer_id,
        "category": body.category,
        "summary": body.summary,
        "detail": body.detail,
        "status": "open",
        "created_by": body.created_by,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _tickets.append(ticket)
    return {"ticket_id": ticket_id, "status": "open"}


@app.post("/tickets/{ticket_id}/comment")
def add_comment(
    ticket_id: str,
    body: CommentAdd,
    authorization: Optional[str] = Header(None),
):
    _check_auth(authorization)

    if not any(t["ticket_id"] == ticket_id for t in _tickets):
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")

    comment = {
        "id": str(uuid.uuid4()),
        "author": body.author,
        "text": body.text,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _comments.setdefault(ticket_id, []).append(comment)
    return {"status": "comment_added", "comment_id": comment["id"]}


@app.post("/tickets/{ticket_id}/close")
def close_ticket(
    ticket_id: str,
    authorization: Optional[str] = Header(None),
):
    _check_auth(authorization)

    for t in _tickets:
        if t["ticket_id"] == ticket_id:
            if t["status"] == "closed":
                raise HTTPException(status_code=409, detail="Ticket already closed")
            t["status"] = "closed"
            return {"ticket_id": ticket_id, "status": "closed"}
    raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")


@app.delete("/tickets/{ticket_id}")
def delete_ticket(
    ticket_id: str,
    authorization: Optional[str] = Header(None),
):
    """Permanently removes the ticket — irreversible in this stub."""
    _check_auth(authorization)

    for i, t in enumerate(_tickets):
        if t["ticket_id"] == ticket_id:
            _tickets.pop(i)
            _comments.pop(ticket_id, None)
            return {"status": "deleted", "ticket_id": ticket_id}
    raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8083)
