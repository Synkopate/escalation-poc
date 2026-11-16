from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Escalation, EscalationEvent

ALLOWED = {
    "created": {"processing", "failed"},
    "processing": {"waiting_for_manager", "failed"},
    "waiting_for_manager": {"response_received", "failed"},
    "response_received": {"completed", "failed"},
    "failed": {"processing", "response_received"},
    "completed": set(),
}


def transition(
    db: Session, escalation: Escalation, target: str, detail: str = ""
) -> None:
    if target not in ALLOWED[escalation.status]:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid transition: {escalation.status} -> {target}",
        )
    previous = escalation.status
    escalation.status = target
    db.add(
        EscalationEvent(
            escalation_id=escalation.id,
            from_status=previous,
            to_status=target,
            detail=detail,
        )
    )
