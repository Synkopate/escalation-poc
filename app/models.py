from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow():
    return datetime.now(UTC)


class Escalation(Base):
    __tablename__ = "escalations"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    ticket_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    agent_id: Mapped[int] = mapped_column(Integer, nullable=False)
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    chat_thread: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    manager_id: Mapped[int | None] = mapped_column(Integer)
    manager_reply: Mapped[str | None] = mapped_column(Text)
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    events: Mapped[list["EscalationEvent"]] = relationship(
        back_populates="escalation", cascade="all, delete-orphan"
    )


Index(
    "uq_active_ticket",
    Escalation.ticket_id,
    unique=True,
    sqlite_where=Escalation.status.in_(
        ["created", "processing", "waiting_for_manager", "response_received", "failed"]
    ),
)


class EscalationEvent(Base):
    __tablename__ = "escalation_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    escalation_id: Mapped[str] = mapped_column(
        ForeignKey("escalations.id"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    escalation: Mapped[Escalation] = relationship(back_populates="events")
