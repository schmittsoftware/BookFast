"""Trajecten (onboarding / conversie / stopzetting): config-driven checklists,
approval-gated document requests, client side effects, tenant isolation."""

from datetime import date

import pytest

from app.services import deadlines, trajecten
from tests.conftest import make_client, make_org

TODAY = date(2026, 7, 5)


def start_traject(db, deps, org, kind="onboarding", email="klant@test.be", meta=None):
    client = make_client(db, org, email)
    return trajecten.start(db, org, client, kind=kind, actor="Tester", meta=meta)


def test_checklist_comes_from_org_config_not_code(db, deps):
    """NFR-07: per-kantoor template per trajecttype, no code change."""
    org = make_org(db, "custom")
    org.traject_templates = {
        "conversie": [{"key": "eigen_stap", "label": "Eigen stap", "kind": "taak"}],
    }
    conversie = start_traject(db, deps, org, kind="conversie", meta={"naar_vorm": "BV"})
    assert [s.key for s in conversie.steps] == ["eigen_stap"]

    # Onboarding has no override → Belgian default.
    onboarding = start_traject(db, deps, org, kind="onboarding", email="tweede@test.be")
    assert [s.key for s in onboarding.steps] == [
        s["key"] for s in trajecten.DEFAULT_TEMPLATES["onboarding"]
    ]


def test_unknown_kind_is_refused(db, deps):
    org = make_org(db, "unknown")
    with pytest.raises(ValueError):
        start_traject(db, deps, org, kind="bestaat-niet")


def test_document_request_creates_draft_not_send(db, deps):
    """FR-31: requesting a document drafts an Action; nothing is sent."""
    org = make_org(db, "kantoor")
    traject = start_traject(db, deps, org)
    step = next(s for s in traject.steps if s.kind == "document")

    action = trajecten.request_document(db, deps, org, step, actor="Tester")

    assert action.status == "draft"
    assert step.status == "opgevraagd"
    assert step.label in action.draft_text
    assert deps.sender.sent == []  # the gate stays closed


def test_step_status_guarded_per_kind(db, deps):
    org = make_org(db, "guard")
    traject = start_traject(db, deps, org, kind="conversie", meta={"naar_vorm": "BV"})
    taak = next(s for s in traject.steps if s.kind == "taak")

    with pytest.raises(ValueError):
        trajecten.set_step_status(db, org, taak, status="ontvangen", actor="Tester")
    trajecten.set_step_status(db, org, taak, status="bezig", actor="Tester")
    trajecten.set_step_status(db, org, taak, status="afgerond", actor="Tester")
    assert taak.status == "afgerond"


def test_onboarding_completion_and_risk_in_meta(db, deps):
    org = make_org(db, "complete")
    org.traject_templates = {
        "onboarding": [
            {"key": "doc", "label": "Document", "kind": "document"},
            {"key": "risico", "label": "Risicoprofiel", "kind": "beslissing"},
        ]
    }
    traject = start_traject(db, deps, org)

    doc = next(s for s in traject.steps if s.kind == "document")
    trajecten.set_step_status(db, org, doc, status="ontvangen", actor="Tester")
    assert traject.status == "bezig"

    trajecten.set_risk_level(db, org, traject, level="laag", actor="Tester")
    assert traject.status == "afgerond"
    assert traject.completed_at is not None
    assert traject.meta["risk_level"] == "laag"


def test_risk_level_only_for_onboarding(db, deps):
    org = make_org(db, "risk-guard")
    conversie = start_traject(db, deps, org, kind="conversie", meta={"naar_vorm": "BV"})
    with pytest.raises(ValueError):
        trajecten.set_risk_level(db, org, conversie, level="laag", actor="Tester")


def test_conversie_completion_updates_client_rechtsvorm(db, deps):
    org = make_org(db, "conversie")
    org.traject_templates = {
        "conversie": [{"key": "akte", "label": "Akte", "kind": "taak"}],
    }
    client = make_client(db, org, "omzet@test.be")
    client.entity_type = "eenmanszaak"
    client.rechtsvorm = "eenmanszaak"
    traject = trajecten.start(
        db,
        org,
        client,
        kind="conversie",
        actor="Tester",
        meta={"van_vorm": "eenmanszaak", "naar_vorm": "BV"},
    )

    trajecten.set_step_status(db, org, traject.steps[0], status="afgerond", actor="Tester")

    assert traject.status == "afgerond"
    assert client.rechtsvorm == "BV"
    assert client.entity_type == "vennootschap"  # deadline rules follow


def test_stopzetting_freezes_client_and_deadlines(db, deps):
    org = make_org(db, "stopzetting")
    org.traject_templates = {
        "stopzetting": [{"key": "afsluiting", "label": "Afsluiten", "kind": "taak"}],
    }
    client = make_client(db, org, "failliet@test.be")
    active_before = {e.client.id for e in deadlines.upcoming(db, org, today=TODAY)}
    assert client.id in active_before

    traject = trajecten.start(
        db, org, client, kind="stopzetting", actor="Tester", meta={"type": "faillissement"}
    )

    assert client.status == "stopzetting"
    # Uit de deadline-bewaking (en dus ook geen escalaties meer).
    assert all(e.client.id != client.id for e in deadlines.upcoming(db, org, today=TODAY))
    assert deadlines.ensure_escalations(db, deps, org, window_days=30, today=TODAY) == []

    trajecten.set_step_status(db, org, traject.steps[0], status="afgerond", actor="Tester")
    assert traject.status == "afgerond"
    assert client.status == "gearchiveerd"


def test_trajecten_are_org_scoped(db, deps):
    org_a = make_org(db, "kantoor-a")
    org_b = make_org(db, "kantoor-b")
    traject_a = start_traject(db, deps, org_a, email="a@klant.be")

    assert trajecten.get(db, org_b, traject_a.id) is None
    step = traject_a.steps[0]
    assert trajecten.get_step(db, org_b, step.id) is None
    with pytest.raises(PermissionError):
        trajecten.request_document(db, deps, org_b, step, actor="Aanvaller")


def test_opdrachtbrief_draft_contains_client_data(db, deps):
    org = make_org(db, "letter")
    client = make_client(db, org, "klant@test.be")
    client.vat_number = "BE 0123.456.789"
    traject = trajecten.start(db, org, client, kind="onboarding", actor="Tester")
    step = next(s for s in traject.steps if s.kind == "opdrachtbrief")

    text = trajecten.generate_opdrachtbrief(db, deps, org, step, actor="Tester")

    assert client.name in text
    assert "BE 0123.456.789" in text
    assert step.status == "opgesteld"
    assert step.note == text
