from enum import Enum
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db

from .models import Escalation, EscalationEvent
from .state import transition

DbSession = Annotated[Session, Depends(get_db)]

app = FastAPI(title="Escalation POC — Milestone 2")
ACTIVE = ("created", "processing", "waiting_for_manager", "response_received", "failed")


class Status(str, Enum):
    created = "created"
    processing = "processing"
    waiting = "waiting_for_manager"
    response_received = "response_received"
    completed = "completed"
    failed = "failed"


class EscalationRequest(BaseModel):
    ticket_id: int = Field(gt=0)
    agent_id: int = Field(gt=0)
    issue: str = Field(min_length=5)


class ManagerReply(BaseModel):
    manager_id: int = Field(gt=0)
    message: str = Field(min_length=1)


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


def serialize(e: Escalation) -> dict:
    return {
        "escalation_id": e.id,
        "ticket_id": e.ticket_id,
        "agent_id": e.agent_id,
        "issue": e.issue,
        "summary": e.summary,
        "chat_thread": e.chat_thread,
        "status": e.status,
        "manager_id": e.manager_id,
        "manager_reply": e.manager_reply,
        "error_detail": e.error_detail,
    }


@app.post("/webhooks/zendesk", status_code=201)
def zendesk_webhook(request: EscalationRequest, db: DbSession):
    existing = db.scalar(
        select(Escalation).where(
            Escalation.ticket_id == request.ticket_id, Escalation.status.in_(ACTIVE)
        )
    )
    if existing:
        return {
            "escalation_id": existing.id,
            "status": existing.status,
            "duplicate": True,
        }
    escalation = Escalation(
        ticket_id=request.ticket_id,
        agent_id=request.agent_id,
        issue=request.issue,
        status="created",
    )
    db.add(escalation)
    db.flush()
    db.add(
        EscalationEvent(
            escalation_id=escalation.id,
            from_status=None,
            to_status="created",
            detail="Mock Zendesk webhook received",
        )
    )
    transition(db, escalation, "processing")
    escalation.summary = mock_claude_summary(mock_ticket_history(request.ticket_id))
    escalation.chat_thread = mock_google_chat_post(escalation.id)
    transition(db, escalation, "waiting_for_manager")
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(Escalation).where(
                Escalation.ticket_id == request.ticket_id, Escalation.status.in_(ACTIVE)
            )
        )
        if existing:
            return {
                "escalation_id": existing.id,
                "status": existing.status,
                "duplicate": True,
            }
        raise
    return {
        "escalation_id": escalation.id,
        "status": escalation.status,
        "chat_thread": escalation.chat_thread,
    }


@app.get("/escalations/{escalation_id}")
def get_escalation(
    escalation_id: str,
    db: DbSession,
):
    escalation = db.get(Escalation, escalation_id)
    if not escalation:
        raise HTTPException(404, "Escalation not found")
    return serialize(escalation)


@app.get("/escalations/{escalation_id}/events")
def get_events(
    escalation_id: str,
    db: DbSession,
):
    if not db.get(Escalation, escalation_id):
        raise HTTPException(404, "Escalation not found")
    events = db.scalars(
        select(EscalationEvent)
        .where(EscalationEvent.escalation_id == escalation_id)
        .order_by(EscalationEvent.id)
    ).all()
    return [
        {
            "from_status": e.from_status,
            "to_status": e.to_status,
            "detail": e.detail,
            "created_at": e.created_at,
        }
        for e in events
    ]


@app.post("/mock/chat-replies/{escalation_id}")
def mock_manager_reply(
    escalation_id: str,
    reply: ManagerReply,
    db: DbSession,
):
    escalation = db.get(Escalation, escalation_id)
    if not escalation:
        raise HTTPException(404, "Escalation not found")
    if escalation.status in ("response_received", "completed"):
        return {"status": escalation.status, "duplicate": True}
    if escalation.status != "waiting_for_manager":
        raise HTTPException(409, f"Cannot reply in state {escalation.status}")
    escalation.manager_id = reply.manager_id
    escalation.manager_reply = reply.message
    transition(
        db,
        escalation,
        "response_received",
        "Manager response stored; Zendesk update pending",
    )
    db.commit()
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


@app.post("/mock/complete/{escalation_id}")
def mock_complete(
    escalation_id: str,
    db: DbSession,
):
    escalation = db.get(Escalation, escalation_id)
    if not escalation:
        raise HTTPException(404, "Escalation not found")
    transition(db, escalation, "completed", "Simulated Zendesk update succeeded")
    db.commit()
    return {"status": escalation.status}
