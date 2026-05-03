"""Mock ITSM HTTP API + Web UI for AAP workflow integration tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Mock ITSM",
    description="In-memory service desk simulation for Ansible Automation Platform workflows.",
    version="1.0.0",
)

tickets: dict[str, dict] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TicketCreate(BaseModel):
    request: str = Field(..., min_length=1, max_length=8000, description="Primary description / request body")
    title: str | None = Field(None, max_length=200)
    priority: str = Field("P3", pattern="^(P1|P2|P3|P4)$")


class TicketUpdate(BaseModel):
    status: str | None = Field(None, max_length=64)
    comment: str | None = Field(None, max_length=4000)


@app.get("/", include_in_schema=False)
async def web_ui():
    path = Path(__file__).resolve().parent / "static" / "index.html"
    if not path.is_file():
        raise HTTPException(status_code=500, detail="static/index.html missing from image")
    return HTMLResponse(path.read_text(encoding="utf-8"), media_type="text/html; charset=utf-8")


@app.post("/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(ticket: TicketCreate):
    ticket_id = str(uuid.uuid4())[:8].upper()
    ts = _now_iso()
    title = (ticket.title or ticket.request[:80] + ("…" if len(ticket.request) > 80 else "")).strip()
    record = {
        "id": ticket_id,
        "title": title,
        "description": ticket.request,
        "status": "NEW",
        "priority": ticket.priority,
        "created_at": ts,
        "updated_at": ts,
        "history": [{"at": ts, "type": "created", "detail": "Ticket registered in mock ITSM."}],
    }
    tickets[ticket_id] = record
    return record


@app.get("/tickets")
def list_tickets():
    items = sorted(tickets.values(), key=lambda t: t["created_at"], reverse=True)
    return {"count": len(items), "tickets": items}


@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    ticket = tickets.get(ticket_id.upper())
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, update: TicketUpdate):
    tid = ticket_id.upper()
    if tid not in tickets:
        raise HTTPException(status_code=404, detail="Ticket not found")
    t = tickets[tid]
    ts = _now_iso()

    if update.status is not None and update.status.strip():
        t["status"] = update.status.strip()
        t["history"].append({"at": ts, "type": "status", "detail": f"Status set to {t['status']}."})

    if update.comment is not None and update.comment.strip():
        t["history"].append({"at": ts, "type": "comment", "detail": update.comment.strip()})

    t["updated_at"] = _now_iso()
    return t


@app.patch("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str):
    tid = ticket_id.upper()
    if tid not in tickets:
        raise HTTPException(status_code=404, detail="Ticket not found")
    t = tickets[tid]
    ts = _now_iso()
    t["status"] = "CLOSED"
    t["history"].append({"at": ts, "type": "closed", "detail": "Ticket closed."})
    t["updated_at"] = ts
    return t
