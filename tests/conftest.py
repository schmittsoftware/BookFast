from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.adapters.drafter_template import TemplateDrafter
from app.adapters.runner_inline import InlineRunner
from app.adapters.storage_local import LocalDiskStorage
from app.config import Settings
from app.container import Deps
from app.db import Base
from app.interfaces import ExtractionResult, FieldExtraction
from app.models import Client, Organization, User


class FakeExtractor:
    """Test double with scriptable confidences."""

    def __init__(self, result: ExtractionResult | None = None, fail: Exception | None = None):
        self.result = result
        self.fail = fail

    def extract(self, *, filename: str, content: bytes, sender: str) -> ExtractionResult:
        if self.fail is not None:
            raise self.fail
        return self.result


class RecordingSender:
    def __init__(self):
        self.sent: list[dict] = []

    def send(self, *, channel: str, recipient: str, subject: str, body: str) -> str:
        self.sent.append(
            {"channel": channel, "recipient": recipient, "subject": subject, "body": body}
        )
        return f"test-{len(self.sent)}"


def make_result(confidences: dict[str, float]) -> ExtractionResult:
    return ExtractionResult(
        doc_type="factuur",
        doc_type_confidence=0.99,
        fields=[
            FieldExtraction(name=n, label=n.capitalize(), value=f"waarde-{n}", confidence=c)
            for n, c in confidences.items()
        ],
        model_version="fake-1",
        prompt_version="t1",
    )


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()


@pytest.fixture
def deps(tmp_path: Path):
    return Deps(
        settings=Settings(storage_dir=tmp_path / "storage", database_url="sqlite://"),
        storage=LocalDiskStorage(tmp_path / "storage"),
        extractor=FakeExtractor(make_result({"totaalbedrag": 0.95})),
        sender=RecordingSender(),
        runner=InlineRunner(),
        drafter=TemplateDrafter(),
    )


def make_org(db, slug: str, threshold: float = 0.85) -> Organization:
    org = Organization(slug=slug, name=f"Kantoor {slug}", confidence_threshold=threshold)
    db.add(org)
    db.flush()
    db.add(User(org_id=org.id, name=f"Tester {slug}", initials="TT"))
    db.commit()
    return org


def make_client(db, org: Organization, email: str) -> Client:
    client = Client(org_id=org.id, name=f"Klant {email}", email=email)
    db.add(client)
    db.commit()
    return client
