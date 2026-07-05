from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.container import Deps
from app.models import Attachment, InboundItem, Organization, User, utcnow
from app.services import intake, review
from app.web.deps import get_db, get_deps, get_org, get_user

router = APIRouter()
templates = Jinja2Templates(directory="../frontend/templates")

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
        "nav": {"review": review_count, "followup": 0, "intake": intake_count},
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
    queue = review.queue(db, org)

    recent_intake = list(
        db.execute(
            select(InboundItem)
            .where(InboundItem.org_id == org.id)
            .order_by(InboundItem.received_at.desc())
            .limit(4)
        ).scalars()
    )

    ctx.update(
        active="dashboard",
        today_label=dutch_date(utcnow()),
        queue=queue[:5],
        queue_total=len(queue),
        recent_intake=recent_intake,
        attention=len(queue),
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
