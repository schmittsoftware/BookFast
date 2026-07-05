"""NFR-06: no code path may expose one kantoor's data to another."""

import pytest

from app.models import Action
from app.services import followup, intake, review
from tests.conftest import FakeExtractor, RecordingSender, make_client, make_org, make_result


def ingest_for(db, deps, org, email):
    make_client(db, org, email)
    deps.extractor = FakeExtractor(make_result({"totaalbedrag": 0.60}))
    item, _ = intake.ingest(
        db,
        deps,
        org,
        channel="email",
        sender=email,
        filename="f.pdf",
        content=b"x" + org.slug.encode(),
        subject="f.pdf",
    )
    return item


def test_review_queue_is_org_scoped(db, deps):
    org_a = make_org(db, "kantoor-a")
    org_b = make_org(db, "kantoor-b")
    item_a = ingest_for(db, deps, org_a, "a@klant.be")
    item_b = ingest_for(db, deps, org_b, "b@klant.be")

    assert [i.id for i in review.queue(db, org_a)] == [item_a.id]
    assert [i.id for i in review.queue(db, org_b)] == [item_b.id]


def test_get_item_cannot_cross_orgs(db, deps):
    org_a = make_org(db, "kantoor-a")
    org_b = make_org(db, "kantoor-b")
    item_a = ingest_for(db, deps, org_a, "a@klant.be")

    assert review.get_item(db, org_b, item_a.id) is None


def test_correcting_another_orgs_extraction_is_refused(db, deps):
    org_a = make_org(db, "kantoor-a")
    org_b = make_org(db, "kantoor-b")
    item_a = ingest_for(db, deps, org_a, "a@klant.be")

    with pytest.raises(PermissionError):
        review.correct_field(
            db,
            org_b,
            item_a.extractions[0],
            field_name="totaalbedrag",
            new_value="1",
            corrected_by="Aanvaller",
        )


def test_sender_matching_never_matches_other_orgs_clients(db, deps):
    """Same email known at kantoor A must stay unmatched at kantoor B (FR-06)."""
    org_a = make_org(db, "kantoor-a")
    org_b = make_org(db, "kantoor-b")
    make_client(db, org_a, "gedeeld@klant.be")
    deps.extractor = FakeExtractor(make_result({"totaalbedrag": 0.99}))

    item_b, _ = intake.ingest(
        db,
        deps,
        org_b,
        channel="email",
        sender="gedeeld@klant.be",
        filename="f.pdf",
        content=b"uniek-b",
        subject="f.pdf",
    )
    assert item_b.match_status == "unconfirmed"
    assert item_b.client_id is None


def test_followup_approval_cannot_cross_orgs(db, deps):
    org_a = make_org(db, "kantoor-a")
    org_b = make_org(db, "kantoor-b")
    client_a = make_client(db, org_a, "a@klant.be")
    action = Action(
        org_id=org_a.id,
        client_id=client_a.id,
        draft_text="tekst",
        channel="email",
    )
    db.add(action)
    db.commit()

    assert followup.get_action(db, org_b, action.id) is None
    with pytest.raises(PermissionError):
        followup.approve_and_send(db, deps, org_b, action, approved_by="Aanvaller")
    assert deps.sender.sent == []


def test_approval_gate_is_the_only_path_to_send(db, deps):
    """FR-31: nothing is sent without an explicit named approval."""
    org = make_org(db, "kantoor-a")
    client = make_client(db, org, "a@klant.be")
    action = Action(org_id=org.id, client_id=client.id, draft_text="Beste, ...", channel="email")
    db.add(action)
    db.commit()

    sender: RecordingSender = deps.sender
    assert sender.sent == []  # drafting alone sends nothing

    followup.approve_and_send(db, deps, org, action, approved_by="Lien")
    assert len(sender.sent) == 1
    assert action.status == "sent"
    assert action.approved_by == "Lien"

    with pytest.raises(ValueError):  # cannot send twice
        followup.approve_and_send(db, deps, org, action, approved_by="Lien")
    assert len(sender.sent) == 1
