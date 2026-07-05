"""Zone A — intake (FR-01..07). Any channel lands here: dedupe, store the raw
original untouched, match the sender, then hand off to processing."""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import Attachment, InboundItem, Organization
from app.services import audit, processing


def ingest(
    db: Session,
    deps: Deps,
    org: Organization,
    *,
    channel: str,
    sender: str,
    filename: str,
    content: bytes,
    content_type: str = "application/octet-stream",
    subject: str = "",
    external_ref: str | None = None,
    source_url: str | None = None,
    source_system: str | None = None,
) -> tuple[InboundItem | None, bool]:
    """Returns (item, is_duplicate). Duplicates are ignored but logged (FR-04)."""

    # Channels without a native message id fall back to a content hash.
    ref = external_ref or f"sha256:{hashlib.sha256(content).hexdigest()}"

    existing = db.execute(
        select(InboundItem).where(
            InboundItem.org_id == org.id,
            InboundItem.channel == channel,
            InboundItem.external_ref == ref,
        )
    ).scalar_one_or_none()
    if existing is not None:
        audit.log(db, org.id, "Systeem", "intake.dedup", f"Duplicaat genegeerd: {filename}")
        db.commit()
        return None, True

    # FR-05: raw original first, before any interpretation.
    storage_key = deps.storage.save(org.id, filename, content)

    item = InboundItem(
        org_id=org.id,
        channel=channel,
        external_ref=ref,
        sender=sender,
        subject=subject,
        source_url=source_url,
        source_system=source_system,
    )
    _match_sender(db, org, item, sender)
    db.add(item)
    db.flush()
    db.add(
        Attachment(
            org_id=org.id,
            inbound_item_id=item.id,
            filename=filename,
            content_type=content_type,
            size=len(content),
            storage_key=storage_key,
        )
    )
    audit.log(
        db,
        org.id,
        "Systeem",
        "intake.received",
        f"Ontving {filename} via {channel}",
        entity_type="inbound_item",
        entity_id=item.id,
    )
    db.commit()

    deps.runner.submit(lambda: processing.process_item(db, deps, org, item))
    return item, False


def _match_sender(db: Session, org: Organization, item: InboundItem, sender: str) -> None:
    """FR-06/FR-07: Sender matching is currently disabled since Client model is removed."""
    item.match_status = "unmatched"
