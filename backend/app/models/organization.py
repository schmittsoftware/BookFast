from sqlalchemy import JSON, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, _id


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_id)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    region: Mapped[str] = mapped_column(String(120), default="")
    employee_count: Mapped[int] = mapped_column(Integer, default=0)
    upload_token: Mapped[str] = mapped_column(String(64), unique=True, default=_id)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.85)
    field_thresholds: Mapped[dict] = mapped_column(JSON, default=dict)
    traject_templates: Mapped[dict] = mapped_column(JSON, default=dict)
