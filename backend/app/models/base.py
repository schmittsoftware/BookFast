import uuid
from datetime import UTC, datetime

from app.db import Base

__all__ = ["Base", "_id", "utcnow"]


def _id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
