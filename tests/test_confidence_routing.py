"""FR-12/13 + NFR-05: per-field confidence decides routing; failures never
disappear."""

from app.services import intake, review
from tests.conftest import FakeExtractor, make_client, make_org, make_result


def ingest(db, deps, org, filename="factuur_test.pdf", sender="klant@test.be", ref=None):
    item, dup = intake.ingest(
        db,
        deps,
        org,
        channel="email",
        sender=sender,
        filename=filename,
        content=b"pdf-bytes-" + filename.encode(),
        subject=filename,
        external_ref=ref,
    )
    return item, dup


def test_all_fields_above_threshold_auto_approves(db, deps):
    org = make_org(db, "auto")
    make_client(db, org, "klant@test.be")
    deps.extractor = FakeExtractor(make_result({"leverancier": 0.95, "totaalbedrag": 0.99}))

    item, _ = ingest(db, deps, org)

    assert item.status == "verified"
    assert item.extractions[0].status == "auto_approved"
    assert item.case_id is not None  # FR-40: grouped immediately
    assert review.queue(db, org) == []


def test_single_low_field_routes_whole_item_to_review(db, deps):
    org = make_org(db, "low")
    make_client(db, org, "klant@test.be")
    deps.extractor = FakeExtractor(
        make_result({"leverancier": 0.99, "totaalbedrag": 0.99, "btw_nummer": 0.60})
    )

    item, _ = ingest(db, deps, org)

    assert item.status == "needs_review"
    assert item.extractions[0].status == "pending_review"
    assert [i.id for i in review.queue(db, org)] == [item.id]


def test_threshold_is_per_org_config(db, deps):
    """FR-14: the same document routes differently per kantoor threshold."""
    strict = make_org(db, "strict", threshold=0.97)
    make_client(db, strict, "klant@test.be")
    deps.extractor = FakeExtractor(make_result({"totaalbedrag": 0.95}))

    item, _ = ingest(db, deps, strict)
    assert item.status == "needs_review"


def test_unknown_sender_forces_review_even_with_high_confidence(db, deps):
    """FR-07: no silent guessing about who sent it."""
    org = make_org(db, "unknown-sender")
    deps.extractor = FakeExtractor(make_result({"totaalbedrag": 0.99}))

    item, _ = ingest(db, deps, org, sender="nooit-gezien@ergens.be")

    assert item.match_status == "unconfirmed"
    assert item.status == "needs_review"


def test_extraction_failure_lands_in_review_queue_not_dropped(db, deps):
    """NFR-05: the failure branch is the review queue, not a dead end."""
    org = make_org(db, "failure")
    make_client(db, org, "klant@test.be")
    deps.extractor = FakeExtractor(fail=RuntimeError("model down"))

    item, _ = ingest(db, deps, org)

    assert item.status == "needs_review"
    extraction = item.extractions[0]
    assert extraction.status == "pending_review"
    assert "model down" in extraction.error
    assert [i.id for i in review.queue(db, org)] == [item.id]


def test_duplicate_external_ref_is_ignored(db, deps):
    """FR-04: channel-native id dedupe."""
    org = make_org(db, "dedupe")
    make_client(db, org, "klant@test.be")

    first, dup1 = ingest(db, deps, org, ref="msg-1")
    second, dup2 = ingest(db, deps, org, ref="msg-1")

    assert dup1 is False and first is not None
    assert dup2 is True and second is None


def test_correction_preserves_original_ai_output(db, deps):
    """FR-22: corrections are recorded against, not over, the AI output."""
    org = make_org(db, "correct")
    make_client(db, org, "klant@test.be")
    deps.extractor = FakeExtractor(make_result({"btw_nummer": 0.60}))

    item, _ = ingest(db, deps, org)
    extraction = item.extractions[0]
    review.correct_field(
        db,
        org,
        extraction,
        field_name="btw_nummer",
        new_value="BE 0123.456.789",
        corrected_by="Tester",
    )

    stored = next(f for f in extraction.fields if f["name"] == "btw_nummer")
    assert stored["value"] == "waarde-btw_nummer"  # original untouched
    assert extraction.corrections[0].corrected_value == "BE 0123.456.789"
    assert extraction.corrections[0].original_value == "waarde-btw_nummer"

    merged = review.effective_fields(extraction)
    shown = next(f for f in merged if f["name"] == "btw_nummer")
    assert shown["corrected_value"] == "BE 0123.456.789"
