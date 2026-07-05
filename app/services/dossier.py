"""Zone E — dossier/case preparation (FR-40..41)."""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Action, AuditLog, Case, InboundItem, Organization


@dataclass
class DossierSummary:
    case: Case
    items: list[InboundItem] = field(default_factory=list)
    verified: int = 0
    in_review: int = 0
    missing: int = 0
    open_actions: list[Action] = field(default_factory=list)
    activity: list[AuditLog] = field(default_factory=list)

    @property
    def expected_total(self) -> int:
        return len(self.items) + self.missing

    @property
    def progress_pct(self) -> int:
        total = self.expected_total
        return round(100 * len(self.items) / total) if total else 0


def list_cases(db: Session, org: Organization) -> list[Case]:
    return list(
        db.execute(select(Case).where(Case.org_id == org.id).order_by(Case.period.desc())).scalars()
    )


def get_case(db: Session, org: Organization, case_id: str) -> Case | None:
    return db.execute(
        select(Case).where(Case.org_id == org.id, Case.id == case_id)
    ).scalar_one_or_none()


def summarize(db: Session, org: Organization, case: Case) -> DossierSummary:
    """FR-41: what's in (verified / in review), what's missing, what's pending."""
    items = list(
        db.execute(
            select(InboundItem)
            .where(InboundItem.org_id == org.id, InboundItem.case_id == case.id)
            .order_by(InboundItem.received_at.asc())
        ).scalars()
    )
    summary = DossierSummary(case=case, items=items)
    summary.verified = sum(1 for i in items if i.status == "verified")
    summary.in_review = sum(1 for i in items if i.status == "needs_review")
    summary.missing = sum(1 for e in case.expected_docs if e.status == "missing")
    summary.open_actions = list(
        db.execute(
            select(Action).where(
                Action.org_id == org.id,
                Action.case_id == case.id,
                Action.status.in_(["draft", "sent"]),
            )
        ).scalars()
    )
    summary.activity = list(
        db.execute(
            select(AuditLog)
            .where(AuditLog.org_id == org.id)
            .order_by(AuditLog.created_at.desc())
            .limit(6)
        ).scalars()
    )
    return summary
