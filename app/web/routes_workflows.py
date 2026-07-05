"""Routes for the Klanten hub (overzicht, onboarding, conversies,
stopzettingen), generic traject details, and the deadline board."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import Client, InboundItem, Organization, Traject, User
from app.services import deadlines, trajecten
from app.web.deps import get_db, get_deps, get_org, get_user
from app.web.routes import base_context, templates

router = APIRouter()


def _klanten_context(request, db, deps, org, user) -> dict:
    ctx = base_context(request, db, deps, org, user)
    ctx.update(
        active="klanten",
        kind_labels=trajecten.KIND_LABELS,
        traject_counts=trajecten.counts_by_kind(db, org),
    )
    return ctx


def _clients(db: Session, org: Organization) -> list[Client]:
    return list(
        db.execute(select(Client).where(Client.org_id == org.id).order_by(Client.name)).scalars()
    )


# ---------- Klanten hub ----------


@router.get("/klanten", response_class=HTMLResponse)
def klanten_index(
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    clients = _clients(db, org)
    open_trajecten = {
        t.client_id: t
        for t in db.execute(
            select(Traject).where(Traject.org_id == org.id, Traject.status == "bezig")
        ).scalars()
    }
    ctx = _klanten_context(request, db, deps, org, user)
    ctx.update(
        subtab="overzicht",
        clients=clients,
        open_trajecten=open_trajecten,
        active_count=sum(1 for c in clients if c.status == "actief"),
    )
    return templates.TemplateResponse(request, "klanten.html", ctx)


@router.post("/klanten")
def klanten_create(
    name: str = Form(...),
    email: str = Form(""),
    vat_number: str = Form(""),
    btw_regime: str = Form("kwartaal"),
    rechtsvorm: str = Form("BV"),
    bookkeeping_software: str = Form(""),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    client = Client(
        org_id=org.id,
        name=name.strip(),
        email=email.strip() or None,
        vat_number=vat_number.strip() or None,
        btw_regime=btw_regime,
        rechtsvorm=rechtsvorm,
        entity_type="eenmanszaak" if rechtsvorm == "eenmanszaak" else "vennootschap",
        bookkeeping_software=bookkeeping_software.strip() or None,
    )
    db.add(client)
    db.flush()
    traject = trajecten.start(db, org, client, kind="onboarding", actor=user.name)
    return RedirectResponse(f"/trajecten/{traject.id}", status_code=303)


@router.get("/klanten/{kind}", response_class=HTMLResponse)
def trajecten_list(
    kind: str,
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    if kind not in trajecten.DEFAULT_TEMPLATES:
        raise HTTPException(404)
    items = trajecten.list_by_kind(db, org, kind)
    busy_client_ids = {t.client_id for t in items if t.status == "bezig"}
    startable = [c for c in _clients(db, org) if c.id not in busy_client_ids]
    if kind == "stopzetting":
        startable = [c for c in startable if c.status == "actief"]
    ctx = _klanten_context(request, db, deps, org, user)
    ctx.update(
        subtab=kind,
        kind=kind,
        trajecten_list=[(t, *trajecten.progress(t)) for t in items],
        startable=startable,
        rechtsvormen=trajecten.RECHTSVORMEN,
    )
    return templates.TemplateResponse(request, "trajecten_list.html", ctx)


@router.post("/klanten/{kind}/start")
def traject_start(
    kind: str,
    client_id: str = Form(...),
    naar_vorm: str = Form(""),
    stopzetting_type: str = Form(""),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    if kind not in trajecten.DEFAULT_TEMPLATES:
        raise HTTPException(404)
    client = db.execute(
        select(Client).where(Client.org_id == org.id, Client.id == client_id)
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404)
    meta: dict = {}
    if kind == "conversie":
        if not naar_vorm or naar_vorm not in trajecten.RECHTSVORMEN:
            raise HTTPException(400, "doelvorm ontbreekt")
        meta = {"van_vorm": client.rechtsvorm or client.entity_type, "naar_vorm": naar_vorm}
    elif kind == "stopzetting":
        meta = {"type": stopzetting_type or "faillissement"}
    traject = trajecten.start(db, org, client, kind=kind, actor=user.name, meta=meta)
    return RedirectResponse(f"/trajecten/{traject.id}", status_code=303)


# ---------- Traject detail ----------


@router.get("/trajecten/{traject_id}", response_class=HTMLResponse)
def traject_detail(
    traject_id: str,
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    traject = trajecten.get(db, org, traject_id)
    if traject is None:
        raise HTTPException(404)
    done, total = trajecten.progress(traject)
    linkable = list(
        db.execute(
            select(InboundItem)
            .where(InboundItem.org_id == org.id, InboundItem.client_id == traject.client_id)
            .order_by(InboundItem.received_at.desc())
            .limit(5)
        ).scalars()
    )
    ctx = _klanten_context(request, db, deps, org, user)
    ctx.update(
        subtab=traject.kind,
        t=traject,
        done=done,
        total=total,
        pct=round(100 * done / total) if total else 0,
        linkable=linkable,
        terminal=trajecten.TERMINAL,
        edit=request.query_params.get("edit") == "1",
    )
    return templates.TemplateResponse(request, "traject.html", ctx)


@router.post("/trajecten/steps/{step_id}/request")
def step_request_document(
    step_id: str,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    step = trajecten.get_step(db, org, step_id)
    if step is None:
        raise HTTPException(404)
    trajecten.request_document(db, deps, org, step, actor=user.name)
    return RedirectResponse(f"/trajecten/{step.traject_id}", status_code=303)


@router.post("/trajecten/steps/{step_id}/status")
def step_set_status(
    step_id: str,
    status: str = Form(...),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    step = trajecten.get_step(db, org, step_id)
    if step is None:
        raise HTTPException(404)
    trajecten.set_step_status(db, org, step, status=status, actor=user.name)
    return RedirectResponse(f"/trajecten/{step.traject_id}", status_code=303)


@router.post("/trajecten/steps/{step_id}/opdrachtbrief")
def step_generate_letter(
    step_id: str,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    step = trajecten.get_step(db, org, step_id)
    if step is None:
        raise HTTPException(404)
    trajecten.generate_opdrachtbrief(db, deps, org, step, actor=user.name)
    return RedirectResponse(f"/trajecten/{step.traject_id}", status_code=303)


@router.post("/trajecten/steps/{step_id}/link")
def step_link_item(
    step_id: str,
    item_id: str = Form(...),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    step = trajecten.get_step(db, org, step_id)
    item = db.execute(
        select(InboundItem).where(InboundItem.org_id == org.id, InboundItem.id == item_id)
    ).scalar_one_or_none()
    if step is None or item is None:
        raise HTTPException(404)
    trajecten.link_item(db, org, step, item, actor=user.name)
    return RedirectResponse(f"/trajecten/{step.traject_id}", status_code=303)


@router.post("/trajecten/{traject_id}/risk")
def set_risk(
    traject_id: str,
    level: str = Form(...),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    traject = trajecten.get(db, org, traject_id)
    if traject is None:
        raise HTTPException(404)
    trajecten.set_risk_level(db, org, traject, level=level, actor=user.name)
    return RedirectResponse(f"/trajecten/{traject_id}", status_code=303)


# ---------- Deadlines ----------


@router.get("/deadlines", response_class=HTMLResponse)
def deadlines_board(
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    deadlines.ensure_escalations(db, deps, org)
    entries = deadlines.upcoming(db, org)

    from collections import defaultdict

    entries_grouped = defaultdict(list)
    for e in entries:
        entries_grouped[e.client].append(e)

    ctx = base_context(request, db, deps, org, user)
    ctx.update(active="deadlines", entries_grouped=dict(entries_grouped))
    return templates.TemplateResponse(request, "deadlines.html", ctx)


@router.get("/deadlines/{client_id}", response_class=HTMLResponse)
def deadlines_detail(
    request: Request,
    client_id: str,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    from app.models import Client

    client = db.execute(
        select(Client).where(Client.id == client_id, Client.org_id == org.id)
    ).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    deadlines.ensure_escalations(db, deps, org)
    all_entries = deadlines.upcoming(db, org)
    client_entries = [e for e in all_entries if e.client.id == client_id]

    ctx = base_context(request, db, deps, org, user)
    ctx.update(active="deadlines", client=client, entries=client_entries)
    return templates.TemplateResponse(request, "deadlines_detail.html", ctx)


@router.post("/deadlines/done")
def deadline_done(
    request: Request,
    client_id: str = Form(...),
    rule_key: str = Form(...),
    period: str = Form(...),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    client = db.execute(
        select(Client).where(Client.org_id == org.id, Client.id == client_id)
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404)
    deadlines.mark_done(db, org, client, rule_key=rule_key, period=period, actor=user.name)
    # Blijf waar je was: afvinken vanaf de detailpagina brengt je daar terug.
    return RedirectResponse(request.headers.get("referer") or "/deadlines", status_code=303)


@router.post("/deadlines/draft")
def deadline_draft(
    request: Request,
    client_id: str = Form(...),
    rule_key: str = Form(...),
    period: str = Form(...),
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    """Handmatig een opvolgconcept aanmaken vanuit een deadline-rij (FR-31:
    het concept wacht op expliciete goedkeuring, er vertrekt niets)."""
    client = db.execute(
        select(Client).where(Client.org_id == org.id, Client.id == client_id)
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404)
    try:
        deadlines.draft_reminder(
            db, deps, org, client, rule_key=rule_key, period=period, actor=user.name
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return RedirectResponse(
        request.headers.get("referer") or f"/deadlines/{client_id}", status_code=303
    )
