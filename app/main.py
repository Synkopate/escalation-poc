from dataclasses import dataclass
from enum import Enum
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Escalation POC")


class Status(str, Enum):
    waiting = "waiting_for_manager"
    resolved = "manager_responded"


class EscalationRequest(BaseModel):
    ticket_id: int = Field(gt=0)
    agent_id: int = Field(gt=0)
    issue: str = Field(min_length=5)


class ManagerReply(BaseModel):
    manager_id: int = Field(gt=0)
    message: str = Field(min_length=1)


@dataclass
class Escalation:
    id: str
    ticket_id: int
    agent_id: int
    issue: str
    summary: str
    chat_thread: str
    status: Status
    manager_reply: str | None = None


# Development-only in-memory storage. Restarting the server clears it.
escalations: dict[str, Escalation] = {}


def mock_ticket_history(ticket_id: int) -> list[str]:
    return [
        f"Ticket {ticket_id}: fictional motorcycle intermittently fails to charge.",
        "Agent verified outlet power and requested connector inspection.",
        "Customer reports the issue persists after inspection.",
    ]


def mock_claude_summary(history: list[str]) -> str:
    return "MOCK SUMMARY: " + " ".join(history)


def mock_google_chat_post(escalation_id: str) -> str:
    return f"spaces/mock-space/threads/{escalation_id}"


@app.post("/webhooks/zendesk", status_code=201)
def zendesk_webhook(request: EscalationRequest):
    # Demo deduplication: one active escalation per ticket.
    for existing in escalations.values():
        if existing.ticket_id == request.ticket_id and existing.status == Status.waiting:
            return {"escalation_id": existing.id, "status": existing.status, "duplicate": True}

    escalation_id = str(uuid4())
    history = mock_ticket_history(request.ticket_id)
    summary = mock_claude_summary(history)
    thread = mock_google_chat_post(escalation_id)
    escalations[escalation_id] = Escalation(
        id=escalation_id,
        ticket_id=request.ticket_id,
        agent_id=request.agent_id,
        issue=request.issue,
        summary=summary,
        chat_thread=thread,
        status=Status.waiting,
    )
    return {"escalation_id": escalation_id, "status": Status.waiting, "chat_thread": thread}


@app.get("/escalations/{escalation_id}")
def get_escalation(escalation_id: str):
    escalation = escalations.get(escalation_id)
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return escalation


@app.post("/mock/chat-replies/{escalation_id}")
def mock_manager_reply(escalation_id: str, reply: ManagerReply):
    escalation = escalations.get(escalation_id)
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if escalation.status == Status.resolved:
        return {"status": escalation.status, "duplicate": True}
    # Simulation only: a real integration must authenticate and authorize the sender.
    escalation.manager_reply = reply.message
    escalation.status = Status.resolved
    return {
        "status": escalation.status,
        "mock_zendesk_action": {
            "ticket_id": escalation.ticket_id,
            "internal_note": reply.message,
            "set_status": "open",
            "remove_tag": "technical_escalation",
            "notify_agent_id": escalation.agent_id,
        },
    }
