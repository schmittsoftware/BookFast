"""Compliance-deadline board (Belgische fiscale kalender).

Deadline *instances* are computed from rules + client config, never stored;
only completions are persisted. When a deadline approaches and the client's
dossier is incomplete, the system drafts a reminder — which, like every
outbound message, waits for human approval (FR-31).

The dates encode the general Belgian calendar (btw: 20e/25e; voorafbetalingen;
jaarrekening 7 maanden na afsluiting; PB via mandataris — indicatief). They are
deliberately rule-level, not per-client tax advice."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import (
    Action,
    Case,
    Client,
    DeadlineCompletion,
    ExpectedDocument,
    InboundItem,
    Organization,
)
from app.services import audit


@dataclass
class DeadlineEntry:
    client: Client
    rule_key: str
    label: str
    period: str
    due: date
    done: bool = False
    dossier_incomplete: bool = False
    missing_labels: list[str] | None = None
    open_action: Action | None = None
    case: Case | None = None

    @property
    def days_left(self) -> int:
        return (self.due - date.today()).days


def _next_btw_maand(today: date) -> tuple[str, date]:
    # Aangifte over maand M is due de 20e van M+1.
    year, month = today.year, today.month
    for _ in range(3):
        due = date(year, month, 20)
        if due >= today:
            prev_month = month - 1 or 12
            prev_year = year - 1 if month == 1 else year
            return f"{prev_year}-{prev_month:02d}", due
        month = month % 12 + 1
        year = year if month != 1 else year + 1
    raise RuntimeError("unreachable")


def _next_btw_kwartaal(today: date) -> tuple[str, date]:
    # Kwartaalaangifte is due de 25e van de maand na het kwartaal.
    candidates = []
    for year in (today.year, today.year + 1):
        for quarter, month in ((1, 4), (2, 7), (3, 10), (4, 1)):
            due_year = year + 1 if month == 1 else year
            candidates.append((f"{year} Q{quarter}", date(due_year, month, 25)))
    return min((c for c in candidates if c[1] >= today), key=lambda c: c[1])


def _next_voorafbetaling(today: date) -> tuple[str, date]:
    for year in (today.year, today.year + 1):
        for idx, (month, day) in enumerate([(4, 10), (7, 10), (10, 10), (12, 20)], start=1):
            due = date(year, month, day)
            if due >= today:
                return f"{year} VA{idx}", due
    raise RuntimeError("unreachable")


def _next_jaarrekening(today: date) -> tuple[str, date]:
    # Neerlegging NBB: binnen 7 maanden na afsluiting boekjaar (31/12 → 31/7).
    year = today.year if today <= date(today.year, 7, 31) else today.year + 1
    return f"boekjaar {year - 1}", date(year, 7, 31)


def _next_personenbelasting(today: date) -> tuple[str, date]:
    # Via mandataris — indicatieve datum, jaarlijks te bevestigen.
    year = today.year if today <= date(today.year, 10, 15) else today.year + 1
    return f"AJ {year}", date(year, 10, 15)


def rules_for(client: Client) -> list[tuple[str, str]]:
    """(rule_key, label) pairs that apply to this client, from client config."""
    rules = []
    if client.btw_regime == "maand":
        rules.append(("btw_maand", "BTW-maandaangifte"))
    elif client.btw_regime == "kwartaal":
        rules.append(("btw_kwartaal", "BTW-kwartaalaangifte"))
    rules.append(("voorafbetaling", "Voorafbetaling"))
    if client.entity_type == "vennootschap":
        rules.append(("jaarrekening", "Jaarrekening (NBB)"))
    else:
        rules.append(("personenbelasting", "Personenbelasting"))
    return rules


_COMPUTE = {
    "btw_maand": _next_btw_maand,
    "btw_kwartaal": _next_btw_kwartaal,
    "voorafbetaling": _next_voorafbetaling,
    "jaarrekening": _next_jaarrekening,
    "personenbelasting": _next_personenbelasting,
}


def _dossier_gaps(db: Session, org: Organization, client: Client) -> list[str]:
    """Labels of missing/unreviewed pieces across the client's dossiers.
    Pilot-level heuristic: period-agnostic — any open gap counts."""
    gaps: list[str] = []
    missing = db.execute(
        select(ExpectedDocument.label)
        .join(Case, ExpectedDocument.case_id == Case.id)
        .where(
            ExpectedDocument.org_id == org.id,
            ExpectedDocument.status == "missing",
            Case.client_id == client.id,
        )
    ).scalars()
    gaps.extend(missing)
    in_review = db.execute(
        select(InboundItem.subject).where(
            InboundItem.org_id == org.id,
            InboundItem.client_id == client.id,
            InboundItem.status == "needs_review",
        )
    ).scalars()
    gaps.extend(f"{s or 'document'} (in review)" for s in in_review)
    return gaps


def upcoming(
    db: Session, org: Organization, *, horizon_days: int = 90, today: date | None = None
) -> list[DeadlineEntry]:
    today = today or date.today()
    # Klanten in stopzetting/gearchiveerd vallen uit de bewaking; hun afhandeling
    # loopt via het stopzettingstraject (services.trajecten).
    clients = list(
        db.execute(
            select(Client)
            .where(Client.org_id == org.id, Client.status == "actief")
            .order_by(Client.name)
        ).scalars()
    )
    completions = {
        (c.client_id, c.rule_key, c.period)
        for c in db.execute(
            select(DeadlineCompletion).where(DeadlineCompletion.org_id == org.id)
        ).scalars()
    }
    entries = []
    for client in clients:
        gaps = _dossier_gaps(db, org, client)
        case = db.execute(
            select(Case)
            .where(Case.org_id == org.id, Case.client_id == client.id)
            .order_by(Case.period.desc())
            .limit(1)
        ).scalar_one_or_none()
        for rule_key, label in rules_for(client):
            period, due = _COMPUTE[rule_key](today)
            if (due - today).days > horizon_days:
                continue
            entry = DeadlineEntry(
                client=client,
                rule_key=rule_key,
                label=label,
                period=period,
                due=due,
                done=(client.id, rule_key, period) in completions,
                dossier_incomplete=bool(gaps),
                missing_labels=gaps,
                case=case,
            )
            entry.open_action = _existing_action(db, org, entry)
            entries.append(entry)
    entries.sort(key=lambda e: (e.due, e.client.name))
    return entries


def _reason_key(entry: DeadlineEntry) -> str:
    return f"Deadline {entry.label} {entry.period}"


def _existing_action(db: Session, org: Organization, entry: DeadlineEntry) -> Action | None:
    return db.execute(
        select(Action).where(
            Action.org_id == org.id,
            Action.client_id == entry.client.id,
            Action.reason == _reason_key(entry),
            Action.status.in_(["draft", "sent"]),
        )
    ).scalar_one_or_none()


def mark_done(
    db: Session, org: Organization, client: Client, *, rule_key: str, period: str, actor: str
) -> None:
    if client.org_id != org.id:
        raise PermissionError("klant behoort niet tot deze organisatie")
    db.add(
        DeadlineCompletion(
            org_id=org.id,
            client_id=client.id,
            rule_key=rule_key,
            period=period,
            completed_by=actor,
        )
    )
    audit.log(
        db,
        org.id,
        actor,
        "deadline.done",
        f"vinkte {rule_key} {period} af voor {client.name}",
        entity_type="client",
        entity_id=client.id,
    )
    db.commit()


def _create_reminder(
    db: Session, deps: Deps, org: Organization, entry: DeadlineEntry, *, actor: str
) -> Action:
    """Draft one reminder for a deadline entry. Never sends — the draft goes
    through the normal FR-31 approval gate like every outbound message."""
    text = deps.drafter.draft(
        "deadline_reminder",
        {
            "client_name": entry.client.name,
            "org_name": org.name,
            "deadline_label": entry.label,
            "period": entry.period,
            "due_date": entry.due.strftime("%d-%m-%Y"),
            "missing_labels": entry.missing_labels,
        },
    )
    action = Action(
        org_id=org.id,
        client_id=entry.client.id,
        case_id=entry.case.id if entry.case else None,
        kind="deadline",
        reason=_reason_key(entry),
        draft_text=text,
        channel="email",
    )
    db.add(action)
    entry.open_action = action
    audit.log(
        db,
        org.id,
        actor,
        "deadline.reminder_drafted",
        f"stelde herinnering op: {entry.label} {entry.period} voor {entry.client.name}",
        entity_type="action",
        entity_id=None,
    )
    return action


def draft_reminder(
    db: Session,
    deps: Deps,
    org: Organization,
    client: Client,
    *,
    rule_key: str,
    period: str,
    actor: str,
) -> Action:
    """Manually draft a reminder from a deadline row — also outside the
    escalation window or with a complete dossier. Idempotent: an existing open
    draft/sent reminder for the same client × rule × period is returned as is."""
    if client.org_id != org.id:
        raise PermissionError("klant behoort niet tot deze organisatie")
    entry = next(
        (
            e
            for e in upcoming(db, org)
            if e.client.id == client.id and e.rule_key == rule_key and e.period == period
        ),
        None,
    )
    if entry is None:
        raise ValueError("deadline niet gevonden binnen de horizon")
    if entry.open_action is not None:
        return entry.open_action
    action = _create_reminder(db, deps, org, entry, actor=actor)
    db.commit()
    return action


def ensure_escalations(
    db: Session,
    deps: Deps,
    org: Organization,
    *,
    window_days: int = 14,
    today: date | None = None,
) -> list[Action]:
    """For deadlines inside the window with an incomplete dossier: draft one
    reminder (idempotent per client × rule × period). Drafts wait for approval."""
    created = []
    for entry in upcoming(db, org, horizon_days=window_days, today=today):
        if entry.done or not entry.dossier_incomplete or entry.open_action is not None:
            continue
        created.append(_create_reminder(db, deps, org, entry, actor="Systeem"))
    if created:
        db.commit()
    return created
