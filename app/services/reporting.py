"""Zone F — reporting / proof of value (FR-50/51)."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Correction, ExtractedData, InboundItem, Organization, utcnow


@dataclass
class WeekdayBar:
    label: str
    auto: int
    manual: int
    is_today: bool = False


@dataclass
class DashboardStats:
    docs_processed: int = 0
    auto_count: int = 0
    manual_count: int = 0
    auto_pct: int = 0
    accuracy_pct: int = 0
    minutes_saved: float = 0.0
    minutes_saved_prev: float = 0.0
    intake_today: int = 0
    weekday_bars: list[WeekdayBar] = field(default_factory=list)

    @property
    def time_saved_label(self) -> str:
        return _fmt_minutes(self.minutes_saved)

    @property
    def time_saved_delta_label(self) -> str:
        return _fmt_minutes(abs(self.minutes_saved - self.minutes_saved_prev))


def _fmt_minutes(minutes: float) -> str:
    hours, mins = divmod(int(minutes), 60)
    return f"{hours}u {mins:02d}m"


def _week_start(now: datetime) -> datetime:
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def dashboard_stats(db: Session, org: Organization, settings: Settings) -> DashboardStats:
    now = utcnow()
    week_start = _week_start(now)
    prev_week_start = week_start - timedelta(days=7)

    def counts(since: datetime, until: datetime) -> tuple[int, int]:
        auto = db.execute(
            select(func.count())
            .select_from(ExtractedData)
            .where(
                ExtractedData.org_id == org.id,
                ExtractedData.status == "auto_approved",
                ExtractedData.created_at >= since,
                ExtractedData.created_at < until,
            )
        ).scalar_one()
        manual = db.execute(
            select(func.count())
            .select_from(ExtractedData)
            .where(
                ExtractedData.org_id == org.id,
                ExtractedData.status.in_(["pending_review", "reviewed"]),
                ExtractedData.created_at >= since,
                ExtractedData.created_at < until,
            )
        ).scalar_one()
        return auto, manual

    auto, manual = counts(week_start, now + timedelta(days=1))
    prev_auto, _ = counts(prev_week_start, week_start)

    stats = DashboardStats(
        docs_processed=auto + manual,
        auto_count=auto,
        manual_count=manual,
        auto_pct=round(100 * auto / (auto + manual)) if auto + manual else 0,
        minutes_saved=auto * settings.minutes_saved_per_auto_doc,
        minutes_saved_prev=prev_auto * settings.minutes_saved_per_auto_doc,
    )

    # FR-51 accuracy: share of extracted fields left untouched by humans (FR-22 data).
    total_fields = db.execute(
        select(ExtractedData.fields).where(
            ExtractedData.org_id == org.id, ExtractedData.created_at >= week_start
        )
    ).scalars()
    field_count = sum(len(f or []) for f in total_fields)
    corrections = db.execute(
        select(func.count())
        .select_from(Correction)
        .where(Correction.org_id == org.id, Correction.created_at >= week_start)
    ).scalar_one()
    stats.accuracy_pct = (
        round(100 * (field_count - corrections) / field_count) if field_count else 100
    )

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    stats.intake_today = db.execute(
        select(func.count())
        .select_from(InboundItem)
        .where(InboundItem.org_id == org.id, InboundItem.received_at >= today_start)
    ).scalar_one()

    labels = ["ma", "di", "wo", "do", "vr"]
    for offset, label in enumerate(labels):
        day = week_start + timedelta(days=offset)
        day_auto, day_manual = counts(day, day + timedelta(days=1))
        stats.weekday_bars.append(
            WeekdayBar(
                label=label, auto=day_auto, manual=day_manual, is_today=day.date() == now.date()
            )
        )
    return stats
