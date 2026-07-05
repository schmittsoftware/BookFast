from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import Action, Attachment, InboundItem, Organization, Traject, User, utcnow
from app.services import deadlines, dossier, followup, intake, reporting, review, trajecten
from app.web.deps import get_db, get_deps, get_org, get_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

DUTCH_DAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
DUTCH_MONTHS = [
    "januari",
    "februari",
    "maart",
    "april",
    "mei",
    "juni",
    "juli",
    "augustus",
    "september",
    "oktober",
    "november",
    "december",
]


def dutch_date(dt: datetime) -> str:
    return (
        f"{DUTCH_DAYS[dt.weekday()].capitalize()} {dt.day} {DUTCH_MONTHS[dt.month - 1]} {dt.year}"
    )


def ago(dt: datetime) -> str:
    delta = utcnow() - dt
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "zonet"
    if minutes < 60:
        return f"{minutes} min geleden"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}u geleden"
    days = hours // 24
    return "gisteren" if days == 1 else f"{days} dagen geleden"


def short_date(dt: datetime) -> str:
    return f"{dt.day:02d} {DUTCH_MONTHS[dt.month - 1][:3]}"


templates.env.filters["ago"] = ago
templates.env.filters["short_date"] = short_date


def base_context(request, db, deps, org, user) -> dict:
    review_count = db.execute(
        select(func.count())
        .select_from(InboundItem)
        .where(InboundItem.org_id == org.id, InboundItem.status == "needs_review")
    ).scalar_one()
    followup_count = db.execute(
        select(func.count())
        .select_from(Action)
        .where(Action.org_id == org.id, Action.status == "draft")
    ).scalar_one()
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    intake_count = db.execute(
        select(func.count())
        .select_from(InboundItem)
        .where(InboundItem.org_id == org.id, InboundItem.received_at >= today)
    ).scalar_one()
    return {
        "request": request,
        "org": org,
        "user": user,
        "nav": {"review": review_count, "followup": followup_count, "intake": intake_count},
    }


def lowest_field(item: InboundItem) -> dict | None:
    """The weakest extracted field — used for queue badges."""
    for extraction in item.extractions:
        if extraction.error:
            return {"label": "Extractie mislukt", "confidence": None}
        fields = extraction.fields or []
        if fields:
            worst = min(fields, key=lambda f: f["confidence"])
            return worst
    return None


@router.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    ctx = base_context(request, db, deps, org, user)
    stats = reporting.dashboard_stats(db, org, deps.settings)
    queue = review.queue(db, org)

    # Deadline-bewaking: escalaties klaarzetten (idempotent) en de komende
    # 14 dagen tonen; urgent = binnen 7 dagen en nog niet afgehandeld.
    deadlines.ensure_escalations(db, deps, org)
    upcoming_deadlines = [e for e in deadlines.upcoming(db, org, horizon_days=14) if not e.done]
    urgent = [e for e in upcoming_deadlines if e.days_left <= 7]

    drafts = followup.pending(db, org)
    recent_intake = list(
        db.execute(
            select(InboundItem)
            .where(InboundItem.org_id == org.id)
            .order_by(InboundItem.received_at.desc())
            .limit(4)
        ).scalars()
    )

    busy_trajecten = list(
        db.execute(
            select(Traject)
            .where(Traject.org_id == org.id, Traject.status == "bezig")
            .order_by(Traject.created_at.desc())
            .limit(3)
        ).scalars()
    )

    ctx.update(
        active="dashboard",
        today_label=dutch_date(utcnow()),
        stats=stats,
        queue=queue[:5],
        queue_total=len(queue),
        drafts=drafts,
        recent_intake=recent_intake,
        deadlines_upcoming=upcoming_deadlines[:5],
        deadlines_total=len(upcoming_deadlines),
        traject_counts=trajecten.counts_by_kind(db, org),
        kind_labels=trajecten.KIND_LABELS,
        busy_trajecten=[(t, *trajecten.progress(t)) for t in busy_trajecten],
        attention=len(queue) + len(drafts) + len(urgent),
        lowest_field=lowest_field,
    )
    return templates.TemplateResponse(request, "dashboard.html", ctx)


@router.get("/dashboard")
def dashboard_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/", status_code=303)


@router.get("/review", response_class=HTMLResponse)
def review_index(
    db: Session = Depends(get_db),
    org: Organization = Depends(get_org),
):
    queue = review.queue(db, org)
    if not queue:
        return RedirectResponse("/", status_code=303)
    return RedirectResponse(f"/review/{queue[0].id}", status_code=303)


@router.get("/review/{item_id}", response_class=HTMLResponse)
def review_detail(
    item_id: str,
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    item = review.get_item(db, org, item_id)
    if item is None:
        raise HTTPException(404)
    queue = review.queue(db, org)
    ids = [i.id for i in queue]
    pos = ids.index(item.id) + 1 if item.id in ids else None
    prev_id = ids[pos - 2] if pos and pos > 1 else None
    next_id = ids[pos] if pos and pos < len(ids) else None

    extraction = item.extractions[0] if item.extractions else None
    fields = review.effective_fields(extraction) if extraction else []
    threshold = org.confidence_threshold
    low_count = sum(1 for f in fields if f["confidence"] < threshold)

    ctx = base_context(request, db, deps, org, user)
    ctx.update(
        active="review",
        item=item,
        extraction=extraction,
        fields=fields,
        threshold=threshold,
        low_count=low_count,
        pos=pos,
        total=len(ids),
        prev_id=prev_id,
        next_id=next_id,
        attachment=item.attachments[0] if item.attachments else None,
    )
    return templates.TemplateResponse(request, "review.html", ctx)


@router.post("/review/{item_id}/correct")
def review_correct(
    item_id: str,
    field_name: str = Form(...),
    new_value: str = Form(...),
    db: Session = Depends(get_db),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    item = review.get_item(db, org, item_id)
    if item is None or not item.extractions:
        raise HTTPException(404)
    review.correct_field(
        db,
        org,
        item.extractions[0],
        field_name=field_name,
        new_value=new_value,
        corrected_by=user.name,
    )
    return RedirectResponse(f"/review/{item_id}", status_code=303)


@router.post("/review/{item_id}/approve")
def review_approve(
    item_id: str,
    db: Session = Depends(get_db),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    item = review.get_item(db, org, item_id)
    if item is None:
        raise HTTPException(404)
    review.approve_item(db, org, item, approved_by=user.name)
    remaining = review.queue(db, org)
    return RedirectResponse(f"/review/{remaining[0].id}" if remaining else "/", status_code=303)


@router.get("/dossiers", response_class=HTMLResponse)
def dossiers_index(
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    cases = dossier.list_cases(db, org)
    summaries = [dossier.summarize(db, org, c) for c in cases]
    ctx = base_context(request, db, deps, org, user)
    ctx.update(active="dossiers", summaries=summaries)
    return templates.TemplateResponse(request, "dossier_list.html", ctx)


@router.get("/dossiers/{case_id}", response_class=HTMLResponse)
def dossier_detail(
    case_id: str,
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    case = dossier.get_case(db, org, case_id)
    if case is None:
        raise HTTPException(404)
    summary = dossier.summarize(db, org, case)
    ctx = base_context(request, db, deps, org, user)
    period_dt = datetime.strptime(case.period, "%Y-%m")
    ctx.update(
        active="dossiers",
        s=summary,
        case=case,
        period_label=f"{DUTCH_MONTHS[period_dt.month - 1].capitalize()} {period_dt.year}",
        lowest_field=lowest_field,
        edit=request.query_params.get("edit") == "1",
    )
    return templates.TemplateResponse(request, "dossier.html", ctx)


@router.post("/dossiers/{case_id}/followup")
def create_followup_for_dossier(
    case_id: str,
    db: Session = Depends(get_db),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    case = dossier.get_case(db, org, case_id)
    if not case:
        raise HTTPException(404)
    followup.create_draft(
        db,
        org,
        case.client,
        case_id=case.id,
        reason=f"Opvolging dossier {case.period}",
        draft_text=(
            "Beste klant,\n\nWe missen nog enkele documenten voor dit dossier. "
            "Kan u deze nog bezorgen?\n\nMet vriendelijke groet."
        ),
        actor=user.name,
    )
    return RedirectResponse(f"/opvolging/{case.client_id}", status_code=303)


@router.get("/opvolging", response_class=HTMLResponse)
def opvolging_index(
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    ctx = base_context(request, db, deps, org, user)

    # Get all actions (drafts and sent) to group by client
    drafts = followup.pending(db, org)
    sent = list(
        db.execute(
            select(Action)
            .where(Action.org_id == org.id, Action.status == "sent")
            .order_by(Action.sent_at.desc())
        ).scalars()
    )

    # Group into summary per client
    clients_summary = {}
    for a in drafts + sent:
        client_id = a.client_id
        if client_id not in clients_summary:
            clients_summary[client_id] = {
                "client": a.client,
                "drafts_count": 0,
                "sent_count": 0,
            }
        if a.status == "draft":
            clients_summary[client_id]["drafts_count"] += 1
        elif a.status == "sent":
            clients_summary[client_id]["sent_count"] += 1

    # Sort clients alphabetically by name
    sorted_summaries = sorted(clients_summary.values(), key=lambda x: x["client"].name.lower())

    ctx.update(
        active="opvolging",
        summaries=sorted_summaries,
    )
    return templates.TemplateResponse(request, "opvolging.html", ctx)


@router.get("/opvolging/{client_id}", response_class=HTMLResponse)
def opvolging_detail(
    client_id: str,
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    ctx = base_context(request, db, deps, org, user)
    from app.models import Client

    client = db.execute(
        select(Client).where(Client.org_id == org.id, Client.id == client_id)
    ).scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Klant niet gevonden")

    drafts = list(
        db.execute(
            select(Action)
            .where(Action.org_id == org.id, Action.client_id == client.id, Action.status == "draft")
            .order_by(Action.created_at.asc())
        ).scalars()
    )

    sent = list(
        db.execute(
            select(Action)
            .where(Action.org_id == org.id, Action.client_id == client.id, Action.status == "sent")
            .order_by(Action.sent_at.desc())
        ).scalars()
    )

    ctx.update(
        active="opvolging",
        client=client,
        drafts=drafts,
        sent=sent,
        drafts_count=len(drafts),
        edit=request.query_params.get("edit") == "1",
    )
    return templates.TemplateResponse(request, "opvolging_detail.html", ctx)


@router.post("/actions/{action_id}/approve")
def action_approve(
    action_id: str,
    request: Request,
    edited_text: str = Form(None),
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
    user: User = Depends(get_user),
):
    action = followup.get_action(db, org, action_id)
    if action is None:
        raise HTTPException(404)
    followup.approve_and_send(db, deps, org, action, approved_by=user.name, edited_text=edited_text)
    return RedirectResponse(request.headers.get("referer") or "/", status_code=303)


@router.get("/files/{attachment_id}")
def serve_file(
    attachment_id: str,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
    org: Organization = Depends(get_org),
):
    # NFR-06: attachment lookup is org-scoped; no cross-tenant file access.
    att = db.execute(
        select(Attachment).where(Attachment.org_id == org.id, Attachment.id == attachment_id)
    ).scalar_one_or_none()
    if att is None:
        raise HTTPException(404)
    content = deps.storage.load(att.storage_key)
    return Response(content=content, media_type=att.content_type)


@router.get("/upload/{token}", response_class=HTMLResponse)
def upload_form(token: str, request: Request, db: Session = Depends(get_db)):
    org = db.execute(
        select(Organization).where(Organization.upload_token == token)
    ).scalar_one_or_none()
    if org is None:
        raise HTTPException(404)
    return templates.TemplateResponse(
        request, "upload.html", {"org": org, "token": token, "done": False}
    )


@router.post("/upload/{token}", response_class=HTMLResponse)
async def upload_submit(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    deps: Deps = Depends(get_deps),
):
    org = db.execute(
        select(Organization).where(Organization.upload_token == token)
    ).scalar_one_or_none()
    if org is None:
        raise HTTPException(404)
    form = await request.form()
    upload = form["document"]
    sender = str(form.get("email", ""))
    content = await upload.read()
    if not content:
        raise HTTPException(400, "Leeg bestand")
    intake.ingest(
        db,
        deps,
        org,
        channel="upload",
        sender=sender,
        filename=upload.filename or "upload",
        content=content,
        content_type=upload.content_type or "application/octet-stream",
        subject=upload.filename or "upload",
    )
    return templates.TemplateResponse(
        request, "upload.html", {"org": org, "token": token, "done": True}
    )
