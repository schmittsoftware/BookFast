"""Zone B — classification & extraction (FR-10..15) plus routing (FR-13).

NFR-05 is enforced structurally here: the only two exits are auto-approved or
the human review queue. Extraction failure is not a separate error path — it is
a pending_review ExtractedData with an error note."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import Case, ExtractedData, InboundItem, Organization
from app.services import audit

logger = logging.getLogger("boekvast.processing")


def threshold_for(org: Organization, field_name: str) -> float:
    """FR-14: per-kantoor default with optional per-field override."""
    return float(org.field_thresholds.get(field_name, org.confidence_threshold))


def process_item(db: Session, deps: Deps, org: Organization, item: InboundItem) -> ExtractedData:
    attachment = item.attachments[0] if item.attachments else None
    try:
        if attachment is None:
            raise ValueError("Geen bijlage gevonden op inbound item")
        content = deps.storage.load(attachment.storage_key)
        result = deps.extractor.extract(
            filename=attachment.filename, content=content, sender=item.sender
        )
        extraction = ExtractedData(
            org_id=org.id,
            inbound_item_id=item.id,
            doc_type=result.doc_type,
            doc_type_confidence=result.doc_type_confidence,
            fields=[f.as_dict() for f in result.fields],
            model_version=result.model_version,
            prompt_version=result.prompt_version,
        )
    except Exception as exc:  # NFR-05: never a silent failure — land in review.
        logger.exception("Extractie mislukt voor item %s", item.id)
        extraction = ExtractedData(
            org_id=org.id,
            inbound_item_id=item.id,
            doc_type="onduidelijk",
            error=str(exc),
            status="pending_review",
        )
        item.status = "needs_review"
        db.add(extraction)
        audit.log(
            db,
            org.id,
            "Systeem",
            "extract.failed",
            "Extractie mislukt — item naar review queue",
            entity_type="inbound_item",
            entity_id=item.id,
        )
        db.commit()
        return extraction

    low_fields = [f for f in extraction.fields if f["confidence"] < threshold_for(org, f["name"])]
    needs_review = (
        bool(low_fields)
        or extraction.doc_type_confidence < org.confidence_threshold
        or extraction.doc_type == "onduidelijk"
        or item.match_status != "matched"  # FR-07: unknown sender needs a human
    )

    if needs_review:
        extraction.status = "pending_review"
        item.status = "needs_review"
        reason = (
            f"{len(low_fields)} veld(en) onder drempel"
            if low_fields
            else "classificatie/afzender onzeker"
        )
        audit.log(
            db,
            org.id,
            "Systeem",
            "extract.routed_review",
            f"{extraction.doc_type} naar review: {reason}",
            entity_type="inbound_item",
            entity_id=item.id,
        )
    else:
        extraction.status = "auto_approved"
        item.status = "verified"
        audit.log(
            db,
            org.id,
            "Systeem",
            "extract.auto_approved",
            f"{extraction.doc_type} automatisch verwerkt",
            entity_type="inbound_item",
            entity_id=item.id,
        )

    _assign_case(db, org, item)
    db.add(extraction)
    db.commit()
    return extraction


def _assign_case(db: Session, org: Organization, item: InboundItem) -> None:
    """FR-40: group per client per period — continuous, not on demand."""
    if item.client_id is None:
        return
    period = item.received_at.strftime("%Y-%m")
    case = db.execute(
        select(Case).where(
            Case.org_id == org.id, Case.client_id == item.client_id, Case.period == period
        )
    ).scalar_one_or_none()
    if case is None:
        case = Case(org_id=org.id, client_id=item.client_id, period=period)
        db.add(case)
        db.flush()
    item.case_id = case.id
