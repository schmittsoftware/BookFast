from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import Organization, User


def get_deps(request: Request) -> Deps:
    return request.app.state.deps


def get_db(request: Request):
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_org(request: Request, db: Session = Depends(get_db)) -> Organization:
    """Pilot phase: no auth yet — the UI is scoped to the configured demo org.
    Every query downstream is still org_id-scoped (NFR-06), so adding real
    sessions later only changes this dependency."""
    slug = request.app.state.deps.settings.demo_org_slug
    org = db.execute(select(Organization).where(Organization.slug == slug)).scalar_one_or_none()
    if org is None:
        raise HTTPException(500, "Demo-organisatie niet gevonden — seed ontbreekt")
    return org


def get_user(db: Session = Depends(get_db), org: Organization = Depends(get_org)) -> User:
    user = db.execute(select(User).where(User.org_id == org.id)).scalars().first()
    if user is None:
        raise HTTPException(500, "Geen gebruiker voor demo-organisatie")
    return user
