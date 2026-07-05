from sqlalchemy.orm import Session

from app.models import AuditLog


def log(
    db: Session,
    org_id: str,
    actor: str,
    event: str,
    detail: str = "",
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        org_id=org_id,
        actor=actor,
        event=event,
        detail=detail,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(entry)
    return entry
