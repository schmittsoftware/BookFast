"""Klanttrajecten: onboarding, rechtsvorm-conversie en stopzetting/faillissement.

One checklist engine for all three (and future kinds — a new traject type is a
config template, not code). Scope boundaries stay hard: document requests to
clients go through the Action + human-approval gate (FR-31); statuses around
notaris/KBO/curator/e604C are *tracked*, never submitted anywhere by the system.

Side effects on the client record are the deliberately-small automation layer:
- conversie afgerond   → client.rechtsvorm/entity_type volgen de doelvorm
- stopzetting gestart  → client.status = "stopzetting" (valt uit deadline-bewaking)
- stopzetting afgerond → client.status = "gearchiveerd"
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import Action, Client, InboundItem, Organization, Traject, TrajectStep, utcnow
from app.services import audit

RECHTSVORMEN = ["eenmanszaak", "VOF", "CommV", "BV", "CV", "NV"]

KIND_LABELS = {
    "onboarding": "Onboarding",
    "conversie": "Rechtsvorm-conversie",
    "stopzetting": "Stopzetting & faillissement",
}

# Belgian default checklists. Per-kantoor overrides live in
# Organization.traject_templates[kind] (NFR-07: config, not code).
DEFAULT_TEMPLATES = {
    "onboarding": [
        {"key": "id_zaakvoerder", "label": "Identiteitsbewijs zaakvoerder", "kind": "document"},
        {"key": "statuten", "label": "Statuten / oprichtingsakte", "kind": "document"},
        {"key": "ubo_uittreksel", "label": "UBO-register uittreksel", "kind": "document"},
        {"key": "risicoprofiel", "label": "Antiwitwas-risicoprofiel", "kind": "beslissing"},
        {"key": "opdrachtbrief", "label": "Opdrachtbrief", "kind": "opdrachtbrief"},
        {"key": "mandaat_taxonweb", "label": "Mandaat Tax-on-web", "kind": "mandaat"},
        {"key": "mandaat_biztax", "label": "Mandaat Biztax", "kind": "mandaat"},
        {"key": "mandaat_intervat", "label": "Mandaat Intervat", "kind": "mandaat"},
    ],
    # Generiek omzettingstraject (WVV boek 14); eenmanszaak→vennootschap wijkt
    # in de praktijk af (oprichting + inbreng) — kantoor past de template aan.
    "conversie": [
        {
            "key": "staat_activa",
            "label": "Staat van activa en passiva (max. 3 maanden oud)",
            "kind": "document",
        },
        {"key": "verslag_bestuur", "label": "Verslag bestuursorgaan", "kind": "document"},
        {"key": "verslag_revisor", "label": "Verslag bedrijfsrevisor", "kind": "document"},
        {"key": "notariele_akte", "label": "Notariële akte van omzetting", "kind": "taak"},
        {"key": "publicatie_bs", "label": "Publicatie Belgisch Staatsblad", "kind": "taak"},
        {"key": "kbo_ubo", "label": "KBO & UBO-register bijwerken", "kind": "taak"},
        {"key": "btw_mandaten", "label": "BTW-regime & mandaten nazien", "kind": "taak"},
    ],
    "stopzetting": [
        {
            "key": "vonnis",
            "label": "Vonnis van faillietverklaring (n.v.t. bij vrijwillige stopzetting)",
            "kind": "document",
        },
        {"key": "curator", "label": "Gegevens curator registreren", "kind": "taak"},
        {
            "key": "boekhouding_overdracht",
            "label": "Boekhouding overdragen aan curator",
            "kind": "taak",
        },
        {
            "key": "afsluiting",
            "label": "Boekjaar afsluiten tot datum stopzetting",
            "kind": "taak",
        },
        {
            "key": "btw_stopzetting",
            "label": "Stopzetting btw-identificatie (e604C) opvolgen",
            "kind": "taak",
        },
        {
            "key": "kbo_uitschrijving",
            "label": "KBO-uitschrijving / vereffening opvolgen",
            "kind": "taak",
        },
    ],
}

# Statuses that count as "this step is finished".
TERMINAL = {"ontvangen", "bepaald", "ondertekend", "actief", "afgerond", "nvt"}

# Which statuses the UI may set per step kind (guarded here, not in templates).
ALLOWED = {
    "document": {"opgevraagd", "ontvangen", "nvt"},
    "beslissing": {"bepaald"},
    "opdrachtbrief": {"opgesteld", "ondertekend", "nvt"},
    "mandaat": {"aangevraagd", "actief", "nvt"},
    "taak": {"bezig", "afgerond", "nvt"},
}


def template_for(org: Organization, kind: str) -> list[dict]:
    if kind not in DEFAULT_TEMPLATES:
        raise ValueError(f"onbekend trajecttype: {kind}")
    return (org.traject_templates or {}).get(kind) or DEFAULT_TEMPLATES[kind]


def start(
    db: Session,
    org: Organization,
    client: Client,
    *,
    kind: str,
    actor: str,
    meta: dict | None = None,
) -> Traject:
    if client.org_id != org.id:
        raise PermissionError("klant behoort niet tot deze organisatie")
    traject = Traject(org_id=org.id, client_id=client.id, kind=kind, meta=meta or {})
    db.add(traject)
    db.flush()
    for position, step in enumerate(template_for(org, kind)):
        db.add(
            TrajectStep(
                org_id=org.id,
                traject_id=traject.id,
                position=position,
                key=step["key"],
                label=step["label"],
                kind=step["kind"],
            )
        )
    if kind == "stopzetting":
        # Uit de actieve bewaking halen: geen deadline-escalaties meer (de
        # afhandeling zelf loopt via dit traject).
        client.status = "stopzetting"
    audit.log(
        db,
        org.id,
        actor,
        f"traject.{kind}.started",
        f"startte {KIND_LABELS[kind].lower()} voor {client.name}",
        entity_type="traject",
        entity_id=traject.id,
    )
    db.commit()
    return traject


def list_by_kind(db: Session, org: Organization, kind: str) -> list[Traject]:
    return list(
        db.execute(
            select(Traject)
            .where(Traject.org_id == org.id, Traject.kind == kind)
            .order_by(Traject.created_at.desc())
        ).scalars()
    )


def counts_by_kind(db: Session, org: Organization) -> dict[str, int]:
    counts = dict.fromkeys(DEFAULT_TEMPLATES, 0)
    for traject in db.execute(
        select(Traject).where(Traject.org_id == org.id, Traject.status == "bezig")
    ).scalars():
        counts[traject.kind] = counts.get(traject.kind, 0) + 1
    return counts


def get(db: Session, org: Organization, traject_id: str) -> Traject | None:
    return db.execute(
        select(Traject).where(Traject.org_id == org.id, Traject.id == traject_id)
    ).scalar_one_or_none()


def get_step(db: Session, org: Organization, step_id: str) -> TrajectStep | None:
    return db.execute(
        select(TrajectStep).where(TrajectStep.org_id == org.id, TrajectStep.id == step_id)
    ).scalar_one_or_none()


def progress(traject: Traject) -> tuple[int, int]:
    done = sum(1 for s in traject.steps if s.status in TERMINAL)
    return done, len(traject.steps)


def request_document(
    db: Session, deps: Deps, org: Organization, step: TrajectStep, *, actor: str
) -> Action:
    """Draft (not send!) a document request to the client. FR-31 applies."""
    if step.org_id != org.id:
        raise PermissionError("stap behoort niet tot deze organisatie")
    if step.kind != "document":
        raise ValueError("alleen documentstappen kunnen opgevraagd worden")
    traject = step.traject
    client = traject.client
    text = deps.drafter.draft(
        "onboarding_document_request",
        {"client_name": client.name, "org_name": org.name, "document_label": step.label},
    )
    action = Action(
        org_id=org.id,
        client_id=client.id,
        kind=traject.kind,
        reason=f"{KIND_LABELS[traject.kind]}: {step.label} opvragen",
        draft_text=text,
        channel="email",
    )
    db.add(action)
    step.status = "opgevraagd"
    audit.log(
        db,
        org.id,
        actor,
        "traject.doc_requested",
        f"maakte concept-opvraging '{step.label}' voor {client.name}",
        entity_type="traject_step",
        entity_id=step.id,
    )
    db.commit()
    return action


def set_step_status(
    db: Session,
    org: Organization,
    step: TrajectStep,
    *,
    status: str,
    actor: str,
    note: str | None = None,
) -> None:
    if step.org_id != org.id:
        raise PermissionError("stap behoort niet tot deze organisatie")
    if status not in ALLOWED[step.kind]:
        raise ValueError(f"status '{status}' niet toegelaten voor stap-type '{step.kind}'")
    step.status = status
    if note:
        step.note = note
    audit.log(
        db,
        org.id,
        actor,
        "traject.step_updated",
        f"zette '{step.label}' op {status} voor {step.traject.client.name}",
        entity_type="traject_step",
        entity_id=step.id,
    )
    _maybe_complete(db, org, step.traject, actor=actor)
    db.commit()


def set_risk_level(
    db: Session, org: Organization, traject: Traject, *, level: str, actor: str
) -> None:
    """Antiwitwas-risicoprofiel (onboarding): a human decision, only recorded."""
    if traject.org_id != org.id:
        raise PermissionError("traject behoort niet tot deze organisatie")
    if traject.kind != "onboarding":
        raise ValueError("risicoprofiel hoort bij een onboarding-traject")
    if level not in {"laag", "standaard", "hoog"}:
        raise ValueError("risiconiveau moet laag, standaard of hoog zijn")
    traject.meta = {**traject.meta, "risk_level": level}
    for step in traject.steps:
        if step.kind == "beslissing":
            step.status = "bepaald"
            step.note = f"Risiconiveau: {level}"
    audit.log(
        db,
        org.id,
        actor,
        "traject.risk_set",
        f"bepaalde risicoprofiel '{level}' voor {traject.client.name}",
        entity_type="traject",
        entity_id=traject.id,
    )
    _maybe_complete(db, org, traject, actor=actor)
    db.commit()


def generate_opdrachtbrief(
    db: Session, deps: Deps, org: Organization, step: TrajectStep, *, actor: str
) -> str:
    """Draft the engagement letter from client data. Stored on the step for
    review/print; it becomes 'ondertekend' only when a human says so."""
    if step.org_id != org.id:
        raise PermissionError("stap behoort niet tot deze organisatie")
    if step.kind != "opdrachtbrief":
        raise ValueError("deze stap is geen opdrachtbrief")
    client = step.traject.client
    text = deps.drafter.draft(
        "opdrachtbrief",
        {"client_name": client.name, "org_name": org.name, "vat_number": client.vat_number},
    )
    step.note = text
    step.status = "opgesteld"
    audit.log(
        db,
        org.id,
        actor,
        "traject.letter_drafted",
        f"stelde opdrachtbrief op voor {client.name}",
        entity_type="traject_step",
        entity_id=step.id,
    )
    db.commit()
    return text


def link_item(
    db: Session, org: Organization, step: TrajectStep, item: InboundItem, *, actor: str
) -> None:
    """Attach a received inbound document to a checklist step."""
    if step.org_id != org.id or item.org_id != org.id:
        raise PermissionError("stap of item behoort niet tot deze organisatie")
    step.inbound_item_id = item.id
    step.status = "ontvangen"
    audit.log(
        db,
        org.id,
        actor,
        "traject.doc_linked",
        f"koppelde '{item.subject or 'document'}' aan stap '{step.label}'",
        entity_type="traject_step",
        entity_id=step.id,
    )
    _maybe_complete(db, org, step.traject, actor=actor)
    db.commit()


def _maybe_complete(db: Session, org: Organization, traject: Traject, *, actor: str) -> None:
    if traject.status == "afgerond":
        return
    if not traject.steps or not all(s.status in TERMINAL for s in traject.steps):
        return
    traject.status = "afgerond"
    traject.completed_at = utcnow()
    client = traject.client
    if traject.kind == "conversie":
        naar = traject.meta.get("naar_vorm")
        if naar:
            client.rechtsvorm = naar
            client.entity_type = "eenmanszaak" if naar == "eenmanszaak" else "vennootschap"
    elif traject.kind == "stopzetting":
        client.status = "gearchiveerd"
    audit.log(
        db,
        org.id,
        actor,
        f"traject.{traject.kind}.completed",
        f"rondde {KIND_LABELS[traject.kind].lower()} af voor {client.name}",
        entity_type="traject",
        entity_id=traject.id,
    )
