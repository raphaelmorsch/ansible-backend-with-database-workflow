from fastapi import FastAPI
from pydantic import BaseModel
import uuid

app = FastAPI()

tickets = {}

class TicketCreate(BaseModel):
    request: str

class TicketUpdate(BaseModel):
    status: str = None
    comment: str = None

@app.post("/tickets")
def create_ticket(ticket: TicketCreate):
    ticket_id = str(uuid.uuid4())[:8]
    tickets[ticket_id] = {
        "id": ticket_id,
        "request": ticket.request,
        "status": "OPEN",
        "updates": []
    }
    return tickets[ticket_id]

@app.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: str, update: TicketUpdate):
    if ticket_id not in tickets:
        return {"error": "not found"}

    if update.status:
        tickets[ticket_id]["status"] = update.status

    if update.comment:
        tickets[ticket_id]["updates"].append(update.comment)

    return tickets[ticket_id]

@app.patch("/tickets/{ticket_id}/close")
def close_ticket(ticket_id: str):
    if ticket_id not in tickets:
        return {"error": "not found"}

    tickets[ticket_id]["status"] = "CLOSED"
    return tickets[ticket_id]

@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    return tickets.get(ticket_id, {"error": "not found"})