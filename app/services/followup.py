"""Zone D — client communication (FR-30..32).

FR-31 is the hard trust boundary: MessageSender is only ever called from
approve_and_send(), which requires a named human approver."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import Action, Client, Organization, utcnow
from app.services import audit


def pending(db: Session, org: Organization) -> list[Action]:
    return list(
        db.execute(
            select(Action)
            .where(Action.org_id == org.id, Action.status == "draft")
            .order_by(Action.created_at.asc())
        ).scalars()
    )


def get_action(db: Session, org: Organization, action_id: str) -> Action | None:
    return db.execute(
        select(Action).where(Action.org_id == org.id, Action.id == action_id)
    ).scalar_one_or_none()


def create_draft(
    db: Session,
    org: Organization,
    client: Client,
    *,
    case_id: str | None = None,
    reason: str = "Handmatige opvolging",
    draft_text: str = "",
    channel: str = "email",
    actor: str,
) -> Action:
    action = Action(
        org_id=org.id,
        client_id=client.id,
        case_id=case_id,
        kind="followup",
        reason=reason,
        draft_text=draft_text,
        channel=channel,
        status="draft",
    )
    db.add(action)
    audit.log(
        db,
        org.id,
        actor,
        "followup.drafted",
        f"handmatig concept klaargezet voor {client.name}",
        entity_type="client",
        entity_id=client.id,
    )
    db.commit()
    return action


def approve_and_send(
    db: Session,
    deps: Deps,
    org: Organization,
    action: Action,
    *,
    approved_by: str,
    edited_text: str | None = None,
) -> None:
    if action.org_id != org.id:
        raise PermissionError("actie behoort niet tot deze organisatie")
    if action.status != "draft":
        raise ValueError("actie is al verzonden of afgehandeld")
    if edited_text:
        action.draft_text = edited_text

    recipient = action.client.email or action.client.phone or ""
    ref = deps.sender.send(
        channel=action.channel,
        recipient=recipient,
        subject=f"Opvolging: {action.reason}" if action.reason else "Opvolging",
        body=action.draft_text,
    )
    action.status = "sent"
    action.approved_by = approved_by
    action.sent_at = utcnow()
    audit.log(
        db,
        org.id,
        approved_by,
        "followup.sent",
        f"keurde opvolgbericht goed aan {action.client.name} ({ref})",
        entity_type="action",
        entity_id=action.id,
    )
    db.commit()


def mark_resolved(db: Session, org: Organization, action: Action, *, actor: str) -> None:
    if action.org_id != org.id:
        raise PermissionError("actie behoort niet tot deze organisatie")
    action.status = "resolved"
    action.resolved_at = utcnow()
    audit.log(
        db,
        org.id,
        actor,
        "followup.resolved",
        f"opvolging opgelost voor {action.client.name}",
        entity_type="action",
        entity_id=action.id,
    )
    db.commit()
