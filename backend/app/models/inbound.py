from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, _id, utcnow


class InboundItem(Base):
    __tablename__ = "inbound_items"
    __table_args__ = (
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

    status: Mapped[str] = mapped_column(String(30), default="received")
    match_status: Mapped[str] = mapped_column(String(30), default="unmatched")

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
    __tablename__ = "extracted_data"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    inbound_item_id: Mapped[str] = mapped_column(ForeignKey("inbound_items.id"), index=True)
    doc_type: Mapped[str] = mapped_column(String(40), default="onduidelijk")
    doc_type_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    fields: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str] = mapped_column(String(60), default="")
    prompt_version: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(30), default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    item: Mapped[InboundItem] = relationship(back_populates="extractions")
    corrections: Mapped[list["Correction"]] = relationship(back_populates="extraction")


class Correction(Base):
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
