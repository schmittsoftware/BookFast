"""Core entities per requirements-analysis §5.

Hard rules encoded here (CLAUDE.md §3):
- Every core entity carries org_id (NFR-06, multi-tenant from day one).
- InboundItem/Attachment hold the raw, immutable intake; AI interpretation lives
  exclusively in ExtractedData (physically separate table, reproducible from raw).
- Extracted fields are schema-flexible JSON, validated in application code.
- Corrections are recorded against the original AI output (FR-22), never as an
  overwrite of it.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    region: Mapped[str] = mapped_column(String(120), default="")
    employee_count: Mapped[int] = mapped_column(Integer, default=0)
    # FR-02: login-free upload form is addressed by an unguessable token per kantoor.
    upload_token: Mapped[str] = mapped_column(String(64), unique=True, default=_id)
    # FR-13/14: threshold configurable per kantoor; per-field overrides in JSON.
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.85)
    field_thresholds: Mapped[dict] = mapped_column(JSON, default=dict)
    # NFR-07: traject checklists are org-level config, not code. Dict keyed by
    # traject kind; a missing key means "use the Belgian default template"
    # (services.trajecten.DEFAULT_TEMPLATES).
    traject_templates: Mapped[dict] = mapped_column(JSON, default=dict)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    initials: Mapped[str] = mapped_column(String(4))


class Source(Base):
    """Channel configuration per kantoor (NFR-07: config-only onboarding)."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))  # email | upload | whatsapp
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(default=True)


class Client(Base):
    """The kantoor's own customer."""

    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    vat_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bookkeeping_software: Mapped[str | None] = mapped_column(String(60), nullable=True)
    client_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Drives which compliance deadlines apply (services.deadlines).
    btw_regime: Mapped[str] = mapped_column(String(20), default="kwartaal")
    # maand | kwartaal | geen
    entity_type: Mapped[str] = mapped_column(String(20), default="vennootschap")
    # vennootschap | eenmanszaak
    rechtsvorm: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # eenmanszaak | VOF | CommV | BV | CV | NV — informatief; entity_type blijft
    # de grove indeling die de deadline-regels stuurt.
    status: Mapped[str] = mapped_column(String(20), default="actief")
    # actief | stopzetting | gearchiveerd — niet-actieve klanten vallen uit de
    # deadline-bewaking (services.deadlines)


class InboundItem(Base):
    """Raw intake record. The raw fields (channel, sender, external_ref, received_at,
    attachments) are written once at ingest and never modified; `status`,
    `match_status` and `client_id`/`case_id` are workflow metadata."""

    __tablename__ = "inbound_items"
    __table_args__ = (
        # FR-04: dedupe on the channel-native message id, scoped per org.
        UniqueConstraint("org_id", "channel", "external_ref", name="uq_inbound_dedupe"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    channel: Mapped[str] = mapped_column(String(30))
    external_ref: Mapped[str] = mapped_column(String(200))
    sender: Mapped[str] = mapped_column(String(200), default="")
    subject: Mapped[str] = mapped_column(String(300), default="")
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_system: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Workflow metadata (not raw content).
    status: Mapped[str] = mapped_column(String(30), default="received")
    # received | needs_review | verified | dismissed
    match_status: Mapped[str] = mapped_column(String(30), default="unmatched")
    # matched | unconfirmed | unmatched  (FR-06/FR-07)
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True)

    client: Mapped[Client | None] = relationship()
    attachments: Mapped[list["Attachment"]] = relationship(back_populates="item")
    extractions: Mapped[list["ExtractedData"]] = relationship(back_populates="item")


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    inbound_item_id: Mapped[str] = mapped_column(ForeignKey("inbound_items.id"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    content_type: Mapped[str] = mapped_column(String(100), default="application/octet-stream")
    size: Mapped[int] = mapped_column(Integer, default=0)
    storage_key: Mapped[str] = mapped_column(String(400))

    item: Mapped[InboundItem] = relationship(back_populates="attachments")


class ExtractedData(Base):
    """AI interpretation of an InboundItem — always reproducible from the raw item.

    `fields` is a JSON list of {name, label, value, confidence, note, suggestion}
    exactly as the extractor produced it; it is never edited afterwards (FR-22 —
    human corrections live in Correction rows)."""

    __tablename__ = "extracted_data"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    inbound_item_id: Mapped[str] = mapped_column(ForeignKey("inbound_items.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40), default="onduidelijk")  # FR-10
    doc_type_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    fields: Mapped[list] = mapped_column(JSON, default=list)  # FR-11/FR-12
    error: Mapped[str | None] = mapped_column(Text, nullable=True)  # NFR-05
    model_version: Mapped[str] = mapped_column(String(60), default="")  # FR-15
    prompt_version: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(30), default="pending_review")
    # pending_review | auto_approved | reviewed
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped[InboundItem] = relationship(back_populates="extractions")
    corrections: Mapped[list["Correction"]] = relationship(back_populates="extraction")


class Correction(Base):
    """FR-22: every human correction, recorded against the original AI output."""

    __tablename__ = "corrections"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    extracted_data_id: Mapped[str] = mapped_column(ForeignKey("extracted_data.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(80))
    original_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    corrected_value: Mapped[str] = mapped_column(Text)
    corrected_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    extraction: Mapped[ExtractedData] = relationship(back_populates="corrections")


class Case(Base):
    """Dossier: groups inbound items per client per period (FR-40)."""

    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    period: Mapped[str] = mapped_column(String(10))  # e.g. "2026-06"
    status: Mapped[str] = mapped_column(String(30), default="open")

    client: Mapped[Client] = relationship()
    expected_docs: Mapped[list["ExpectedDocument"]] = relationship(back_populates="case")


class ExpectedDocument(Base):
    """What a dossier expects per period; drives missing-document detection (FR-30)."""

    __tablename__ = "expected_documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), index=True)
    label: Mapped[str] = mapped_column(String(200))
    rule: Mapped[str] = mapped_column(String(60), default="monthly")
    status: Mapped[str] = mapped_column(String(30), default="missing")  # missing | received

    case: Mapped[Case] = relationship(back_populates="expected_docs")


class Action(Base):
    """AI-drafted outbound work awaiting human sign-off. FR-31: nothing sends
    without explicit approval — enforced by the service layer, `status` can only
    reach 'sent' through approve()."""

    __tablename__ = "actions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30), default="followup")
    reason: Mapped[str] = mapped_column(String(300), default="")
    draft_text: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(30), default="email")
    status: Mapped[str] = mapped_column(String(30), default="draft")
    # draft | sent | resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    approved_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    client: Mapped[Client] = relationship()
    case: Mapped["Case"] = relationship()


class AuditLog(Base):
    """NFR-03: who/what changed which thing, when."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    actor: Mapped[str] = mapped_column(String(120))  # user name or "Systeem"
    event: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(Text, default="")
    entity_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Traject(Base):
    """Generic client journey: a checklist-driven dossier of a given kind —
    onboarding (antiwitwas/KYC, opdrachtbrief, mandaten), rechtsvorm-conversie,
    or stopzetting/faillissement. Steps come from org config per kind; kind-
    specific data (risicoprofiel, van/naar-vorm, type stopzetting) lives in
    `meta`."""

    __tablename__ = "trajecten"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    # onboarding | conversie | stopzetting
    status: Mapped[str] = mapped_column(String(20), default="bezig")  # bezig | afgerond
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    client: Mapped[Client] = relationship()
    steps: Mapped[list["TrajectStep"]] = relationship(
        back_populates="traject", order_by="TrajectStep.position"
    )


class TrajectStep(Base):
    __tablename__ = "traject_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    traject_id: Mapped[str] = mapped_column(ForeignKey("trajecten.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    key: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30))
    # document | beslissing | opdrachtbrief | mandaat | taak
    status: Mapped[str] = mapped_column(String(30), default="open")
    # document:      open → opgevraagd → ontvangen (of nvt)
    # beslissing:    open → bepaald
    # opdrachtbrief: open → opgesteld → ondertekend
    # mandaat:       open → aangevraagd → actief (of nvt)
    # taak:          open → bezig → afgerond (of nvt)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    inbound_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("inbound_items.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    traject: Mapped[Traject] = relationship(back_populates="steps")


class DeadlineCompletion(Base):
    """Marks one compliance deadline (client × rule × period) as handled.
    Deadline instances themselves are computed, not stored."""

    __tablename__ = "deadline_completions"
    __table_args__ = (
        UniqueConstraint("org_id", "client_id", "rule_key", "period", name="uq_deadline_done"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id"), index=True)
    rule_key: Mapped[str] = mapped_column(String(60))
    period: Mapped[str] = mapped_column(String(20))
    completed_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
