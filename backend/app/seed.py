"""Demo seed for the pilot demo/dev environment. Creates one kantoor with
realistic in-flight data so every screen has content. Only runs on an empty DB."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import (
    Attachment,
    InboundItem,
    ExtractedData,
    Organization,
    Source,
    User,
    utcnow,
)
from app.services import audit


def _facsimile(vendor: str, client: str, amount: str, date_label: str, vat: str) -> bytes:
    """A simple HTML invoice stand-in stored as the raw attachment, so the review
    screen's 'original document' pane shows a real stored file."""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>body{{font-family:'Helvetica Neue',Arial,sans-serif;color:#3A3D36;font-size:12px;margin:26px}}
.h{{display:flex;justify-content:space-between;margin-bottom:24px}}
.brand{{font-size:19px;font-weight:700;color:#5B2C8A}}
.label{{font-size:9.5px;color:#B0B3A8;text-transform:uppercase;letter-spacing:.5px;margin:12px 0 5px}}
table{{width:100%;border-collapse:collapse;margin-top:14px}}
td{{padding:9px 0;border-bottom:1px solid #F2EFE6;font-size:11.5px}}
.tot{{text-align:right;font-weight:700;font-size:13px}}</style></head><body>
<div class="h"><div><div class="brand">{vendor.lower()}</div></div>
<div style="text-align:right"><b>FACTUUR</b></div></div>
<div class="label">Gefactureerd aan</div><div>{client}</div>
<div class="label">BTW</div><div><b>{vat}</b></div>
<div class="label">Factuurdatum</div><div>{date_label}</div>
<table><tr><td>Diensten/leveringen</td><td style="text-align:right">{amount}</td></tr>
<tr><td class="tot">Totaal</td><td class="tot" style="text-align:right">{amount}</td></tr></table>
</body></html>""".encode()


def _field(name: str, label: str, value: str, conf: float, note=None, suggestion=None) -> dict:
    return {
        "name": name,
        "label": label,
        "value": value,
        "confidence": conf,
        "note": note,
        "suggestion": suggestion,
    }


def seed_if_empty(db: Session, deps: Deps) -> None:
    if db.execute(select(Organization)).first() is not None:
        return

    now = utcnow()

    org = Organization(
        slug=deps.settings.demo_org_slug,
        name="Kantoor Van Loon",
        region="Kempen",
        employee_count=8,
        upload_token="demo-van-loon",
        confidence_threshold=deps.settings.default_confidence_threshold,
    )
    db.add(org)
    db.flush()

    db.add(User(org_id=org.id, name="Lien", initials="LV"))
    for channel in ("email", "upload", "whatsapp"):
        db.add(Source(org_id=org.id, channel=channel, config={}))

    def item(
        channel,
        filename,
        subject,
        received,
        status,
        *,
        sender=None,
        match="unmatched",
        external_ref=None,
        source_url=None,
        source_system=None,
        content: bytes | None = None,
        content_type="text/html",
    ) -> InboundItem:
        it = InboundItem(
            org_id=org.id,
            channel=channel,
            external_ref=external_ref or f"seed-{filename}-{received.timestamp()}",
            sender=sender or "onbekend@voorbeeld.be",
            subject=subject,
            received_at=received,
            status=status,
            match_status=match,
            source_url=source_url,
            source_system=source_system,
        )
        db.add(it)
        db.flush()
        raw = content or _facsimile(
            subject, "Onbekend", "€ 0,00", "juni 2026", "BE —"
        )
        key = deps.storage.save(org.id, filename, raw)
        db.add(
            Attachment(
                org_id=org.id,
                inbound_item_id=it.id,
                filename=filename,
                content_type=content_type,
                size=len(raw),
                storage_key=key,
            )
        )
        return it

    def extraction(
        it, doc_type, doc_conf, fields, status, created=None, model="gpt-4o", prompt="v3"
    ):
        ed = ExtractedData(
            org_id=org.id,
            inbound_item_id=it.id,
            doc_type=doc_type,
            doc_type_confidence=doc_conf,
            fields=fields,
            status=status,
            model_version=model,
            prompt_version=prompt,
            created_at=created or it.received_at,
        )
        db.add(ed)
        return ed

    # ---- Review queue (needs_review), mirroring the design's dashboard rows ----
    telenet = item(
        "email",
        "factuur_telenet_jun.pdf",
        "Telenet BVBA",
        now - timedelta(minutes=8),
        "needs_review",
        sender="facturatie@telenet.be",
        external_ref="A-20614",
        source_url="https://outlook.office.com/mail/inbox/id/A-20614",
        source_system="Outlook",
        content=_facsimile(
            "telenet", "De Wit Consulting BV", "€ 144,45", "12 juni 2026", "BE 0648.925.130"
        ),
    )
    extraction(
        telenet,
        "factuur",
        0.99,
        [
            _field("leverancier", "Leverancier", "Telenet BVBA", 0.96),
            _field("totaalbedrag", "Totaalbedrag", "€ 144,45", 0.98),
            _field("factuurdatum", "Factuurdatum", "12-06-2026", 0.95),
            _field(
                "btw_nummer",
                "BTW-nummer",
                "BE 0648.925.130",
                0.61,
                note="Laatste 3 cijfers onzeker — mogelijk 310 i.p.v. 130",
                suggestion="BE 0648.925.310",
            ),
        ],
        "pending_review",
    )

    db.commit()
