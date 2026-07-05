"""Deadline board: Belgian calendar rules, idempotent approval-gated
escalations, tenant isolation."""

from datetime import date

from app.models import Case, ExpectedDocument
from app.services import deadlines, followup
from tests.conftest import make_client, make_org

TODAY = date(2026, 7, 5)


def test_btw_maand_due_20th_next_month(db, deps):
    org = make_org(db, "btw-maand")
    client = make_client(db, org, "m@klant.be")
    client.btw_regime = "maand"
    db.commit()

    entries = deadlines.upcoming(db, org, today=TODAY)
    btw = next(e for e in entries if e.rule_key == "btw_maand")
    assert btw.period == "2026-06"
    assert btw.due == date(2026, 7, 20)


def test_btw_kwartaal_due_25th_after_quarter(db, deps):
    org = make_org(db, "btw-kw")
    make_client(db, org, "k@klant.be")  # default kwartaal

    entries = deadlines.upcoming(db, org, today=TODAY)
    btw = next(e for e in entries if e.rule_key == "btw_kwartaal")
    assert btw.period == "2026 Q2"
    assert btw.due == date(2026, 7, 25)


def test_rules_follow_client_config(db, deps):
    org = make_org(db, "rules")
    venn = make_client(db, org, "v@klant.be")
    eenmans = make_client(db, org, "e@klant.be")
    eenmans.entity_type = "eenmanszaak"
    eenmans.btw_regime = "geen"
    db.commit()

    entries = deadlines.upcoming(db, org, horizon_days=365, today=TODAY)
    venn_keys = {e.rule_key for e in entries if e.client.id == venn.id}
    eenmans_keys = {e.rule_key for e in entries if e.client.id == eenmans.id}
    assert "jaarrekening" in venn_keys and "personenbelasting" not in venn_keys
    assert "personenbelasting" in eenmans_keys and "btw_kwartaal" not in eenmans_keys


def test_escalation_drafts_once_and_never_sends(db, deps):
    """FR-31 + idempotency: incomplete dossier near deadline → exactly one draft."""
    org = make_org(db, "escalate")
    client = make_client(db, org, "e@klant.be")
    case = Case(org_id=org.id, client_id=client.id, period="2026-06")
    db.add(case)
    db.flush()
    db.add(
        ExpectedDocument(org_id=org.id, case_id=case.id, label="Bankafschrift juni", rule="monthly")
    )
    db.commit()

    created = deadlines.ensure_escalations(db, deps, org, window_days=30, today=TODAY)
    again = deadlines.ensure_escalations(db, deps, org, window_days=30, today=TODAY)

    assert len(created) >= 1
    assert again == []  # idempotent
    assert all(a.status == "draft" for a in created)
    assert deps.sender.sent == []  # nothing auto-sent
    assert "Bankafschrift juni" in created[0].draft_text
    # The draft is approvable through the normal gate.
    followup.approve_and_send(db, deps, org, created[0], approved_by="Lien")
    assert len(deps.sender.sent) == 1


def test_complete_dossier_gets_no_escalation(db, deps):
    org = make_org(db, "quiet")
    make_client(db, org, "q@klant.be")
    created = deadlines.ensure_escalations(db, deps, org, window_days=30, today=TODAY)
    assert created == []


def test_manual_draft_works_with_complete_dossier_and_is_idempotent(db, deps):
    """Handmatig concept vanaf de deadline-rij: ook zonder dossier-gaps en
    buiten het escalatievenster; nooit dubbel, nooit auto-verzonden (FR-31)."""
    org = make_org(db, "manual")
    client = make_client(db, org, "m@klant.be")

    # Auto-escalation does nothing here (dossier complete)...
    assert deadlines.ensure_escalations(db, deps, org, window_days=30, today=TODAY) == []

    # ...but a manual draft is allowed.
    first = deadlines.draft_reminder(
        db, deps, org, client, rule_key="btw_kwartaal", period="2026 Q2", actor="Lien"
    )
    again = deadlines.draft_reminder(
        db, deps, org, client, rule_key="btw_kwartaal", period="2026 Q2", actor="Lien"
    )
    assert first.status == "draft"
    assert again.id == first.id  # idempotent
    assert deps.sender.sent == []  # nothing sent without approval

    entry = next(
        e
        for e in deadlines.upcoming(db, org, today=TODAY)
        if e.rule_key == "btw_kwartaal" and e.client.id == client.id
    )
    assert entry.open_action is not None and entry.open_action.id == first.id

    followup.approve_and_send(db, deps, org, first, approved_by="Lien")
    assert len(deps.sender.sent) == 1


def test_manual_draft_is_org_scoped(db, deps):
    org_a = make_org(db, "kantoor-a")
    org_b = make_org(db, "kantoor-b")
    client_a = make_client(db, org_a, "a@klant.be")

    import pytest

    with pytest.raises(PermissionError):
        deadlines.draft_reminder(
            db, deps, org_b, client_a, rule_key="btw_kwartaal", period="2026 Q2", actor="X"
        )


def test_mark_done_hides_and_is_org_scoped(db, deps):
    org_a = make_org(db, "kantoor-a")
    org_b = make_org(db, "kantoor-b")
    client_a = make_client(db, org_a, "a@klant.be")

    deadlines.mark_done(
        db, org_a, client_a, rule_key="btw_kwartaal", period="2026 Q2", actor="Lien"
    )
    entry = next(
        e
        for e in deadlines.upcoming(db, org_a, today=TODAY)
        if e.rule_key == "btw_kwartaal" and e.client.id == client_a.id
    )
    assert entry.done is True

    # Org B sees nothing of org A's clients or completions.
    assert all(e.client.org_id == org_b.id for e in deadlines.upcoming(db, org_b, today=TODAY))
