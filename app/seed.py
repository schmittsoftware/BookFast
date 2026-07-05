"""Demo seed for the pilot demo/dev environment. Creates one kantoor with
realistic in-flight data so every screen has content. Only runs on an empty DB."""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import (
    Action,
    Attachment,
    Case,
    Client,
    ExpectedDocument,
    ExtractedData,
    InboundItem,
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

    def client(name, email=None, phone=None, vat=None, software=None, since=None):
        c = Client(
            org_id=org.id,
            name=name,
            email=email,
            phone=phone,
            vat_number=vat,
            bookkeeping_software=software,
            client_since=since,
        )
        db.add(c)
        db.flush()
        return c

    dewit = client(
        "De Wit Consulting BV",
        email="boekhouding@dewitconsulting.be",
        vat="BE 0648.925.310",
        software="Yuki",
        since=datetime(2023, 3, 1),
    )
    janssens = client("Janssens Bouw", email="info@janssensbouw.be", software="Silverfin")
    peeters = client(
        "Peeters & Partners", email="admin@peeters-partners.be", software="Exact Online"
    )
    claes = client("Claes Interieur", email="sofie@claesinterieur.be", software="Yuki")
    vermeulen = client(
        "Vermeulen Transport", email="planning@vermeulentransport.be", software="Yuki"
    )
    mertens = client("Mertens Advocaten", email="kantoor@mertensadvocaten.be", software="Silverfin")

    def case_for(cl: Client, period: str) -> Case:
        c = Case(org_id=org.id, client_id=cl.id, period=period)
        db.add(c)
        db.flush()
        return c

    case_dewit = case_for(dewit, "2026-06")
    case_janssens = case_for(janssens, "2026-07")
    case_peeters = case_for(peeters, "2026-07")

    def item(
        cl,
        channel,
        filename,
        subject,
        received,
        status,
        *,
        case=None,
        sender=None,
        match="matched",
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
            sender=sender or (cl.email if cl else "onbekend@voorbeeld.be"),
            subject=subject,
            received_at=received,
            status=status,
            match_status=match,
            client_id=cl.id if cl else None,
            case_id=case.id if case else None,
            source_url=source_url,
            source_system=source_system,
        )
        db.add(it)
        db.flush()
        raw = content or _facsimile(
            subject, cl.name if cl else "Onbekend", "€ 0,00", "juni 2026", "BE —"
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
        dewit,
        "email",
        "factuur_telenet_jun.pdf",
        "Telenet BVBA",
        now - timedelta(minutes=8),
        "needs_review",
        case=case_dewit,
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

    luminus = item(
        janssens,
        "email",
        "luminus_energie_jun.pdf",
        "Luminus",
        now - timedelta(minutes=22),
        "needs_review",
        case=case_janssens,
        content=_facsimile(
            "luminus", "Janssens Bouw", "€ 302,17", "28 juni 2026", "BE 0401.912.663"
        ),
    )
    extraction(
        luminus,
        "factuur",
        0.97,
        [
            _field("leverancier", "Leverancier", "Luminus", 0.95),
            _field(
                "totaalbedrag",
                "Totaalbedrag",
                "€ 302,17",
                0.74,
                note="Bedrag deels onleesbaar op scan",
            ),
            _field("factuurdatum", "Factuurdatum", "28-06-2026", 0.93),
            _field("btw_nummer", "BTW-nummer", "BE 0401.912.663", 0.91),
        ],
        "pending_review",
    )

    bon = item(
        None,
        "whatsapp",
        "IMG_4821.jpg",
        "Bon",
        now - timedelta(minutes=35),
        "needs_review",
        sender="+32 478 55 12 09",
        match="unconfirmed",
        content_type="image/jpeg",
        content=b"placeholder-image-bytes",
    )
    extraction(
        bon,
        "onduidelijk",
        0.58,
        [
            _field("leverancier", "Leverancier", "—", 0.40, note="Foto onscherp"),
            _field("totaalbedrag", "Totaalbedrag", "€ 46,80", 0.66),
        ],
        "pending_review",
        model="stub-1",
        prompt="v1",
    )

    proximus = item(
        peeters,
        "email",
        "proximus_jun_2026.pdf",
        "Proximus",
        now - timedelta(hours=1),
        "needs_review",
        case=case_peeters,
        content=_facsimile(
            "proximus", "Peeters & Partners", "€ 89,99", "30 juni 2026", "BE 0202.239.951"
        ),
    )
    extraction(
        proximus,
        "factuur",
        0.98,
        [
            _field("leverancier", "Leverancier", "Proximus", 0.97),
            _field("totaalbedrag", "Totaalbedrag", "€ 89,99", 0.96),
            _field(
                "factuurdatum",
                "Factuurdatum",
                "30-06-2026",
                0.68,
                note="Datum en vervaldatum staan dicht bij elkaar",
            ),
            _field("btw_nummer", "BTW-nummer", "BE 0202.239.951", 0.92),
        ],
        "pending_review",
    )

    vraag = item(
        claes,
        "email",
        "vraag_btw_verlegd.eml",
        "Vraag · e-mail",
        now - timedelta(hours=2),
        "needs_review",
        content=b"Dag, geldt de verlegging van BTW ook voor onze verbouwing?",
        content_type="message/rfc822",
    )
    extraction(vraag, "vraag", 0.62, [], "pending_review")

    total_energies = item(
        dewit,
        "whatsapp",
        "bon_total_energies.jpg",
        "Total Energies",
        datetime(2026, 6, 19, 14, 5),
        "needs_review",
        case=case_dewit,
        sender="boekhouding@dewitconsulting.be",
        content_type="image/jpeg",
        content=b"placeholder-bon-total",
    )
    extraction(
        total_energies,
        "bon",
        0.94,
        [
            _field("leverancier", "Leverancier", "Total Energies", 0.93),
            _field("totaalbedrag", "Totaalbedrag", "€ 88,20", 0.71, note="Bedrag onzeker"),
            _field("factuurdatum", "Factuurdatum", "19-06-2026", 0.90),
        ],
        "pending_review",
    )

    # ---- Verified documents in the De Wit June dossier ----
    colruyt = item(
        dewit,
        "email",
        "factuur_2026-06_colruyt.pdf",
        "Colruyt Group",
        datetime(2026, 6, 3, 8, 41),
        "verified",
        case=case_dewit,
        content=_facsimile(
            "colruyt", "De Wit Consulting BV", "€ 284,10", "3 juni 2026", "BE 0400.378.485"
        ),
    )
    extraction(
        colruyt,
        "factuur",
        0.99,
        [
            _field("leverancier", "Leverancier", "Colruyt Group", 0.98),
            _field("totaalbedrag", "Totaalbedrag", "€ 284,10", 0.97),
            _field("factuurdatum", "Factuurdatum", "03-06-2026", 0.96),
            _field("btw_nummer", "BTW-nummer", "BE 0400.378.485", 0.95),
        ],
        "auto_approved",
        created=datetime(2026, 6, 3, 8, 44),
    )

    fluvius = item(
        dewit,
        "upload",
        "fluvius_juni.pdf",
        "Fluvius",
        datetime(2026, 6, 8, 10, 12),
        "verified",
        case=case_dewit,
        content=_facsimile(
            "fluvius", "De Wit Consulting BV", "€ 512,66", "8 juni 2026", "BE 0477.445.084"
        ),
    )
    fluvius_ed = extraction(
        fluvius,
        "factuur",
        0.98,
        [
            _field("leverancier", "Leverancier", "Fluvius", 0.97),
            _field("totaalbedrag", "Totaalbedrag", "€ 512,66", 0.95),
            _field("factuurdatum", "Factuurdatum", "08-06-2026", 0.94),
            _field("btw_nummer", "BTW-nummer", "BE 0477.445.084", 0.79),
        ],
        "reviewed",
        created=datetime(2026, 6, 8, 10, 15),
    )

    # Missing bank statement + follow-up already sent after approval (FR-30..32).
    db.add(
        ExpectedDocument(
            org_id=org.id,
            case_id=case_dewit.id,
            label="Bankafschrift juni",
            rule="monthly",
        )
    )
    db.add(
        Action(
            org_id=org.id,
            client_id=dewit.id,
            case_id=case_dewit.id,
            reason="Bankafschrift juni ontbreekt",
            draft_text="Beste, voor de afsluiting van juni 2026 missen we nog uw bankafschrift. "
            "Kan u dit bezorgen via de gebruikelijke weg?",
            channel="email",
            status="sent",
            approved_by="Lien",
            created_at=datetime(2026, 7, 2, 8, 40),
            sent_at=datetime(2026, 7, 2, 9, 14),
            opened_at=datetime(2026, 7, 2, 11, 2),
        )
    )

    # Drafts awaiting approval (FR-31 gate) — visible on the dashboard.
    db.add(
        Action(
            org_id=org.id,
            client_id=vermeulen.id,
            reason="Factuur nutsvoorziening ontbreekt",
            draft_text="Beste, voor de afsluiting van juni missen we nog uw factuur van de "
            "nutsvoorziening. Kan u deze bezorgen?",
            channel="email",
            status="draft",
            created_at=now - timedelta(hours=3),
        )
    )
    db.add(
        Action(
            org_id=org.id,
            client_id=mertens.id,
            reason="Onkostennota's Q2 ontbreken",
            draft_text="Beste, de onkostennota's voor Q2 ontbreken nog in uw dossier. "
            "Mogen we die verwachten vóór 15 juli?",
            channel="email",
            status="draft",
            created_at=now - timedelta(hours=5),
        )
    )

    # ---- Bulk auto-processed items this week, for the KPI row and weekday chart ----
    vendors = ["Colruyt", "Bol.com", "Vlaio", "Engie", "Base", "Brico", "Q8", "Ikea"]
    clients_cycle = [janssens, peeters, claes, vermeulen, mertens, dewit]
    week_monday = (now - timedelta(days=now.weekday())).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    counter = 0
    for day_offset, per_day in [(0, 7), (1, 9), (2, 10)]:  # ma, di, wo
        day = week_monday + timedelta(days=day_offset)
        if day.date() > now.date():
            break
        for j in range(per_day):
            counter += 1
            cl = clients_cycle[counter % len(clients_cycle)]
            vendor = vendors[counter % len(vendors)]
            received = day + timedelta(minutes=17 * j)
            if received > now:
                continue
            it = item(
                cl,
                "email" if counter % 3 else "upload",
                f"factuur_{vendor.lower()}_{counter}.pdf",
                vendor,
                received,
                "verified",
                content=_facsimile(
                    vendor, cl.name, f"€ {80 + counter},00", "juni 2026", "BE 0999.000.111"
                ),
            )
            extraction(
                it,
                "factuur",
                0.97,
                [
                    _field("leverancier", "Leverancier", vendor, 0.96),
                    _field("totaalbedrag", "Totaalbedrag", f"€ {80 + counter},00", 0.95),
                    _field("factuurdatum", "Factuurdatum", received.strftime("%d-%m-%Y"), 0.94),
                    _field("btw_nummer", "BTW-nummer", "BE 0999.000.111", 0.92),
                ],
                "auto_approved",
            )

    # A couple of manually handled ones this week (for the auto/manual split).
    for k in range(3):
        received = week_monday + timedelta(days=1, hours=3, minutes=40 * k)
        it = item(
            clients_cycle[k],
            "email",
            f"scan_onduidelijk_{k}.pdf",
            "Scan",
            received,
            "verified",
        )
        extraction(
            it,
            "factuur",
            0.90,
            [
                _field("leverancier", "Leverancier", "—", 0.60),
                _field("totaalbedrag", "Totaalbedrag", f"€ {40 + k},50", 0.88),
            ],
            "reviewed",
        )

    # ---- Audit trail entries matching the design's activity feed ----
    audit.log(
        db,
        org.id,
        "Systeem",
        "intake.received",
        "ontving Colruyt-factuur via e-mail",
        "inbound_item",
        colruyt.id,
    ).created_at = datetime(2026, 6, 3, 8, 41)
    audit.log(
        db,
        org.id,
        "Lien",
        "review.corrected",
        "corrigeerde BTW-nr op Fluvius-factuur",
        "extracted_data",
        None,
    ).created_at = now - timedelta(days=1, hours=2)
    audit.log(
        db,
        org.id,
        "Systeem",
        "case.grouped",
        "groepeerde 3 nieuwe items in dossier juni",
        "case",
        case_dewit.id,
    ).created_at = now - timedelta(days=1, hours=8)

    from app.models import Correction

    db.flush()
    if fluvius_ed is not None:
        db.add(
            Correction(
                org_id=org.id,
                extracted_data_id=fluvius_ed.id,
                field_name="btw_nummer",
                original_value="BE 0477.445.084",
                original_confidence=0.79,
                corrected_value="BE 0477.445.048",
                corrected_by="Lien",
                created_at=now - timedelta(days=1, hours=2),
            )
        )

    # ---- Traject demos: onboarding, rechtsvorm-conversie, stopzetting ----
    from app.services import trajecten

    # Rechtsvormen op de bestaande klanten (informatief).
    for cl, vorm in [
        (dewit, "BV"),
        (janssens, "BV"),
        (peeters, "NV"),
        (claes, "eenmanszaak"),
        (vermeulen, "BV"),
        (mertens, "VOF"),
    ]:
        cl.rechtsvorm = vorm
    claes.entity_type = "eenmanszaak"

    # Onboarding: nieuwe klant halverwege de checklist.
    bakkerij = client(
        "Bakkerij Peeters BV",
        email="info@bakkerijpeeters.be",
        vat="BE 0712.334.881",
        software="Billit",
    )
    bakkerij.btw_regime = "maand"
    bakkerij.rechtsvorm = "BV"
    ob = trajecten.start(db, org, bakkerij, kind="onboarding", actor="Lien")
    for step in ob.steps:
        if step.key == "id_zaakvoerder":
            step.status = "ontvangen"
        elif step.key == "statuten":
            step.status = "opgevraagd"
        elif step.key == "mandaat_taxonweb":
            step.status = "aangevraagd"
    trajecten.set_risk_level(db, org, ob, level="standaard", actor="Lien")

    # Conversie: Claes Interieur zet eenmanszaak om naar BV.
    conversie = trajecten.start(
        db,
        org,
        claes,
        kind="conversie",
        actor="Lien",
        meta={"van_vorm": "eenmanszaak", "naar_vorm": "BV"},
    )
    for step in conversie.steps:
        if step.key == "staat_activa":
            step.status = "ontvangen"
        elif step.key == "verslag_bestuur":
            step.status = "opgevraagd"
        elif step.key == "notariele_akte":
            step.status = "bezig"
            step.note = "Afspraak notaris 12 augustus"

    # Stopzetting: faillissement Garage Smets — klant valt uit de bewaking.
    smets = client(
        "Garage Smets BV",
        email="info@garagesmets.be",
        vat="BE 0455.881.204",
        software="Exact Online",
    )
    smets.rechtsvorm = "BV"
    stopzetting = trajecten.start(
        db,
        org,
        smets,
        kind="stopzetting",
        actor="Lien",
        meta={"type": "faillissement"},
    )
    for step in stopzetting.steps:
        if step.key == "vonnis":
            step.status = "ontvangen"
        elif step.key == "curator":
            step.status = "afgerond"
            step.note = "Mr. Vandenberghe, Turnhout"

    db.commit()
