"""Zone C — human review (FR-20..22)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Correction, ExtractedData, InboundItem, Organization
from app.services import audit


def queue(db: Session, org: Organization) -> list[InboundItem]:
    return list(
        db.execute(
            select(InboundItem)
            .where(InboundItem.org_id == org.id, InboundItem.status == "needs_review")
            .order_by(InboundItem.received_at.desc())
        ).scalars()
    )


def get_item(db: Session, org: Organization, item_id: str) -> InboundItem | None:
    return db.execute(
        select(InboundItem).where(InboundItem.org_id == org.id, InboundItem.id == item_id)
    ).scalar_one_or_none()


def effective_fields(extraction: ExtractedData) -> list[dict]:
    """Original AI output merged with any human corrections for display.
    The stored `fields` JSON itself is never rewritten (FR-22)."""
    latest: dict[str, Correction] = {}
    for corr in sorted(extraction.corrections, key=lambda c: c.created_at):
        latest[corr.field_name] = corr
    merged = []
    for f in extraction.fields:
        f = dict(f)
        corr = latest.get(f["name"])
        if corr is not None:
            f["corrected_value"] = corr.corrected_value
            f["corrected_by"] = corr.corrected_by
        merged.append(f)
    return merged


def correct_field(
    db: Session,
    org: Organization,
    extraction: ExtractedData,
    *,
    field_name: str,
    new_value: str,
    corrected_by: str,
) -> Correction:
    if extraction.org_id != org.id:
        raise PermissionError("extraction behoort niet tot deze organisatie")
    original = next((f for f in extraction.fields if f["name"] == field_name), None)
    corr = Correction(
        org_id=org.id,
        extracted_data_id=extraction.id,
        field_name=field_name,
        original_value=original["value"] if original else None,
        original_confidence=original["confidence"] if original else 0.0,
        corrected_value=new_value,
        corrected_by=corrected_by,
    )
    db.add(corr)
    label = original["label"] if original else field_name
    audit.log(
        db,
        org.id,
        corrected_by,
        "review.corrected",
        f"corrigeerde {label}: '{corr.original_value}' → '{new_value}'",
        entity_type="extracted_data",
        entity_id=extraction.id,
    )
    db.commit()
    return corr


def approve_item(db: Session, org: Organization, item: InboundItem, *, approved_by: str) -> None:
    if item.org_id != org.id:
        raise PermissionError("item behoort niet tot deze organisatie")
    item.status = "verified"
    for extraction in item.extractions:
        if extraction.status == "pending_review":
            extraction.status = "reviewed"
            
    # Auto-resolve related follow-up actions if case is now complete
    if item.case_id:
        from app.models import Case
        from app.services import followup
        from app.services.dossier import summarize
        
        case = db.execute(select(Case).where(Case.id == item.case_id)).scalar_one_or_none()
        if case:
            s = summarize(db, org, case)
            if s.missing == 0:
                for action in s.open_actions:
                    followup.mark_resolved(db, org, action, actor="Systeem")

    audit.log(
        db,
        org.id,
        approved_by,
        "review.approved",
        f"keurde item goed ({item.subject or 'document'})",
        entity_type="inbound_item",
        entity_id=item.id,
    )
    db.commit()
