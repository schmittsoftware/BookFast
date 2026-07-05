from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _id


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    vat_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bookkeeping_software: Mapped[str | None] = mapped_column(String(60), nullable=True)
    client_since: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    btw_regime: Mapped[str] = mapped_column(String(20), default="kwartaal")
    entity_type: Mapped[str] = mapped_column(String(20), default="vennootschap")
    rechtsvorm: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="actief")
