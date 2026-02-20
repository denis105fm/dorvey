"""Analytics API: metrics, postback, summary."""

import json
from datetime import datetime, timedelta
from typing import List
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

import asyncio

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.doorway import Doorway, DoorwayMetrics
from app.models.campaign import Campaign
from app.models.setting import Setting
from app.schemas.analytics import (
    DoorwayMetricsCreate,
    DoorwayMetricsResponse,
    PostbackRequest,
    AnalyticsSummary,
    AnalyticsDailyResponse,
    DailyMetricsPoint,
    AnalyticsCampaignsResponse,
    CampaignPerformance,
    DoorwayProfitMetric,
    AnalyticsDoorwaysMetricsResponse,
)

router = APIRouter()


async def _check_doorway_access(db: AsyncSession, doorway_id: int, user_id: int) -> bool:
    r = await db.execute(
        select(Doorway).join(Campaign).where(
            Doorway.id == doorway_id, Campaign.user_id == user_id
        )
    )
    return r.scalar_one_or_none() is not None


@router.get("/doorway/{doorway_id}/metrics", response_model=List[DoorwayMetricsResponse])
async def get_doorway_metrics(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    ok = await _check_doorway_access(db, doorway_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Doorway not found")
    since = datetime.utcnow() - timedelta(days=days)
    r = await db.execute(
        select(DoorwayMetrics)
        .where(DoorwayMetrics.doorway_id == doorway_id, DoorwayMetrics.date >= since)
        .order_by(DoorwayMetrics.date.desc())
    )
    return list(r.scalars().all())


@router.post("/doorway/{doorway_id}/metrics", response_model=DoorwayMetricsResponse)
async def upsert_doorway_metrics(
    doorway_id: int,
    data: DoorwayMetricsCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ok = await _check_doorway_access(db, doorway_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Doorway not found")
    day_start = data.date.replace(hour=0, minute=0, second=0, microsecond=0) if hasattr(data.date, "replace") else data.date
    day_end = day_start + timedelta(days=1)
    r = await db.execute(
        select(DoorwayMetrics).where(
            DoorwayMetrics.doorway_id == doorway_id,
            DoorwayMetrics.date >= day_start,
            DoorwayMetrics.date < day_end,
        )
    )
    m = r.scalar_one_or_none()
    if m:
        m.impressions = data.impressions
        m.clicks = data.clicks
        m.ctr = data.ctr
        m.avg_position = data.avg_position
        m.conversions = data.conversions
        m.revenue = data.revenue
    else:
        m = DoorwayMetrics(doorway_id=doorway_id, **data.model_dump())
        db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


# Bot filter: track postbacks per doorway per minute
import time
_postback_cache: dict[tuple[int, int], int] = {}
def _check_postback_rate(doorway_id: int, max_per_minute: int = 20) -> bool:
    """Return True if postback should be accepted (not suspected bot)."""
    now_min = int(time.time() // 60)
    key = (doorway_id, now_min)
    count = _postback_cache.get(key, 0)
    if count >= max_per_minute:
        return False
    _postback_cache[key] = count + 1
    # Cleanup keys older than 5 min
    cutoff = int(time.time() // 60) - 5
    for k in list(_postback_cache):
        if k[1] < cutoff:
            del _postback_cache[k]
    return True


@router.post("/postback")
@router.get("/postback")
async def postback(
    sub_id: str | None = Query(None, alias="sub_id"),
    payout: float | None = Query(None, alias="payout"),
    db: AsyncSession = Depends(get_db),
):
    """
    Postback from affiliate network. sub_id = doorway_id.
    GET: ?sub_id=123&payout=10.5  or  POST with same query params.
    Bot filter: rejects if > 20 postbacks/min per doorway.
    """
    try:
        doorway_id = int(sub_id or "0")
    except ValueError:
        return {"status": "ignored", "reason": "invalid sub_id"}
    if doorway_id > 0 and not _check_postback_rate(doorway_id):
        return {"status": "ignored", "reason": "rate_limit_suspected_bot"}
    if doorway_id <= 0:
        return {"status": "ignored", "reason": "sub_id required"}
    r = await db.execute(select(Doorway).where(Doorway.id == doorway_id))
    dw = r.scalar_one_or_none()
    if not dw:
        return {"status": "ignored", "reason": "doorway not found"}
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    r2 = await db.execute(
        select(DoorwayMetrics).where(
            DoorwayMetrics.doorway_id == doorway_id,
            DoorwayMetrics.date >= today,
            DoorwayMetrics.date < tomorrow,
        )
    )
    m = r2.scalar_one_or_none()
    if m:
        m.conversions += 1
        m.revenue += payout or 0
    else:
        m = DoorwayMetrics(
            doorway_id=doorway_id,
            date=today,
            conversions=1,
            revenue=payout or 0,
        )
        db.add(m)
    await db.commit()
    uid = None
    try:
        r3 = await db.execute(
            select(Campaign.user_id).join(Doorway, Doorway.campaign_id == Campaign.id).where(Doorway.id == doorway_id)
        )
        uid = r3.scalar()
        if uid:
            from app.services.webhook_service import notify_webhooks
            await notify_webhooks(db, uid, "doorway.conversion", {
                "doorway_id": doorway_id, "payout": payout or 0,
            })
    except Exception:
        pass

    # Forward to Voluum/Binom S2S postback if configured
    if uid:
        cred_r = await db.execute(
            select(Setting).where(
                Setting.user_id == uid,
                Setting.key.in_(["voluum_api_url", "binom_api_url"]),
            )
        )
        urls = {s.key: (s.value or "").strip() for s in cred_r.scalars().all()}
        for key, base in urls.items():
            if not base:
                continue
            fwd_url = base.rstrip("/")
            if "postback" not in fwd_url.lower():
                fwd_url += "/postback"
            sep = "&" if "?" in fwd_url else "?"
            fwd_url += f"{sep}cid={sub_id}&payout={payout or 0}"
            dest = key
            async def _forward(url: str, tracker: str):
                try:
                    import httpx
                    async with httpx.AsyncClient() as c:
                        await c.get(url, timeout=5.0)
                except Exception:
                    pass
            asyncio.create_task(_forward(fwd_url, dest))

    return {"status": "ok", "doorway_id": doorway_id}


def _append_sub_id(url: str, doorway_id: int) -> str:
    """Add sub_id=doorway_id to URL."""
    if not url or doorway_id <= 0:
        return url
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs["sub_id"] = [str(doorway_id)]
    return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))


# 1x1 transparent GIF for visit pixel
_PIXEL_GIF = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x01D\x00;"


@router.get("/visit")
async def visit_pixel(
    dw: int = Query(..., alias="dw", description="doorway_id"),
    vid: str | None = Query(None, alias="vid", description="visitor_id from localStorage"),
    db: AsyncSession = Depends(get_db),
):
    """Track page visit for remarketing. Returns 1x1 transparent GIF. No auth."""
    from fastapi.responses import Response
    from app.models.visitor import VisitorEvent

    if vid and len(vid) <= 64 and vid.replace("-", "").replace("_", "").isalnum():
        r = await db.execute(select(Doorway).where(Doorway.id == dw))
        door = r.scalar_one_or_none()
        if door:
            ev = VisitorEvent(visitor_id=vid, doorway_id=dw, campaign_id=door.campaign_id, event_type="visit")
            db.add(ev)
            await db.commit()
    return Response(content=_PIXEL_GIF, media_type="image/gif")


@router.get("/click")
async def click_redirect(
    dw: int = Query(..., alias="dw", description="doorway_id"),
    vid: str | None = Query(None, alias="vid", description="visitor_id for remarketing"),
    geo: str | None = Query(None, description="Country code for GEO offer routing"),
    device: str | None = Query(None, description="mobile|desktop for device offer routing"),
    db: AsyncSession = Depends(get_db),
):
    """
    Click tracking: redirect to affiliate URL with sub_id, increment DoorwayMetrics.clicks.
    Use as CTA href when click_tracking_enabled and api_base_url are set.
    """
    doorway_id = dw
    r = await db.execute(
        select(Doorway, Campaign)
        .join(Campaign, Doorway.campaign_id == Campaign.id)
        .where(Doorway.id == doorway_id)
    )
    row = r.first()
    if not row:
        raise HTTPException(status_code=404, detail="Doorway not found")
    door, camp = row
    aff_url = camp.affiliate_url
    if not aff_url:
        raise HTTPException(status_code=400, detail="No affiliate URL")
    from app.models.offer import Offer
    off_r = await db.execute(
        select(Offer)
        .where(Offer.campaign_id == camp.id, Offer.is_active == True)
        .order_by(Offer.priority.desc())
    )
    offers_list = [{"url": o.url, "geo": o.geo, "device": o.device, "priority": o.priority, "is_active": o.is_active} for o in off_r.scalars().all()]
    if offers_list:
        from app.services.deploy import _get_best_offer_url
        best = _get_best_offer_url(offers_list, geo=geo, device=device)
        if best:
            aff_url = best
    target = _append_sub_id(aff_url, doorway_id)
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    r2 = await db.execute(
        select(DoorwayMetrics).where(
            DoorwayMetrics.doorway_id == doorway_id,
            DoorwayMetrics.date >= today,
            DoorwayMetrics.date < today + timedelta(days=1),
        )
    )
    m = r2.scalar_one_or_none()
    if m:
        m.clicks = (m.clicks or 0) + 1
    else:
        m = DoorwayMetrics(doorway_id=doorway_id, date=today, clicks=1)
        db.add(m)
    if vid and len(vid) <= 64 and vid.replace("-", "").replace("_", "").isalnum():
        from app.models.visitor import VisitorEvent
        ev = VisitorEvent(
            visitor_id=vid, doorway_id=doorway_id, campaign_id=camp.id,
            event_type="click", meta={"geo": geo, "device": device},
        )
        db.add(ev)
    await db.commit()
    return RedirectResponse(url=target, status_code=302)


class EmailCaptureRequest(BaseModel):
    email: str
    visitor_id: str | None = None
    doorway_id: int


class PushSubscribeRequest(BaseModel):
    visitor_id: str
    doorway_id: int
    subscription: dict


@router.post("/push-subscribe")
async def push_subscribe(
    data: PushSubscribeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save web push subscription for remarketing. No auth (called from page)."""
    from app.models.visitor import PushSubscription, VisitorEvent

    if len(data.visitor_id) > 64 or not data.visitor_id.replace("-", "").replace("_", "").replace(".", "").isalnum():
        raise HTTPException(400, "Invalid visitor_id")
    r = await db.execute(
        select(Doorway).where(Doorway.id == data.doorway_id)
    )
    dw = r.scalar_one_or_none()
    if not dw:
        raise HTTPException(404, "Doorway not found")
    sub = PushSubscription(
        visitor_id=data.visitor_id,
        doorway_id=data.doorway_id,
        campaign_id=dw.campaign_id,
        subscription=data.subscription,
    )
    db.add(sub)
    ev = VisitorEvent(
        visitor_id=data.visitor_id,
        doorway_id=data.doorway_id,
        campaign_id=dw.campaign_id,
        event_type="push_subscribe",
    )
    db.add(ev)
    await db.commit()
    return {"status": "ok"}


@router.post("/email-capture")
async def email_capture(
    data: EmailCaptureRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save email lead for remarketing. No auth (called from page)."""
    import re
    from app.models.visitor import EmailLead

    email = (data.email or "").strip().lower()
    if not email or len(email) > 255:
        raise HTTPException(400, "Invalid email")
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        raise HTTPException(400, "Invalid email format")
    if data.visitor_id and (len(data.visitor_id) > 64 or not data.visitor_id.replace("-", "").replace("_", "").replace(".", "").isalnum()):
        raise HTTPException(400, "Invalid visitor_id")
    r = await db.execute(select(Doorway).where(Doorway.id == data.doorway_id))
    dw = r.scalar_one_or_none()
    if not dw:
        raise HTTPException(404, "Doorway not found")
    lead = EmailLead(
        email=email,
        visitor_id=data.visitor_id or None,
        doorway_id=data.doorway_id,
        campaign_id=dw.campaign_id,
    )
    db.add(lead)
    await db.commit()
    return {"status": "ok"}


class SendPushRequest(BaseModel):
    campaign_id: int | None = None
    doorway_id: int | None = None
    title: str
    body: str
    url: str | None = None


@router.post("/send-push")
async def send_push(
    data: SendPushRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Send push notification to all subscribers of campaign or doorway."""
    from app.models.visitor import PushSubscription

    if not data.campaign_id and not data.doorway_id:
        raise HTTPException(400, "campaign_id or doorway_id required")
    subq = select(Doorway.id).join(Campaign).where(Campaign.user_id == current_user.id)
    if data.campaign_id:
        subq = subq.where(Doorway.campaign_id == data.campaign_id)
    if data.doorway_id:
        subq = subq.where(Doorway.id == data.doorway_id)
    subq = subq.scalar_subquery()
    r = await db.execute(
        select(PushSubscription).where(PushSubscription.doorway_id.in_(subq))
    )
    subs = r.scalars().all()
    if not subs:
        return {"status": "ok", "sent": 0, "message": "Нет подписок"}
    set_r = await db.execute(
        select(Setting).where(
            Setting.user_id == current_user.id,
            Setting.key == "vapid_private_key",
        )
    )
    priv_row = set_r.scalar_one_or_none()
    if not priv_row or not priv_row.value:
        raise HTTPException(400, "VAPID ключи не настроены. Сгенерируйте в Настройках.")
    try:
        from pywebpush import webpush
    except ImportError:
        raise HTTPException(503, "pywebpush не установлен")
    payload = {"title": data.title, "body": data.body, "url": data.url or "/"}
    payload_json = json.dumps(payload, ensure_ascii=False)
    vapid_priv = priv_row.value
    claims = {"sub": "mailto:admin@dorvey.local"}

    def _send_one(sub_info: dict) -> bool:
        try:
            webpush(
                subscription_info=sub_info,
                data=payload_json,
                vapid_private_key=vapid_priv,
                vapid_claims=claims,
            )
            return True
        except Exception:
            return False

    sent = 0
    for s in subs:
        ok = await asyncio.to_thread(_send_one, s.subscription)
        if ok:
            sent += 1
    return {"status": "ok", "sent": sent, "total": len(subs)}


@router.get("/email-leads")
async def get_email_leads(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(90, ge=1, le=365),
    campaign_id: int | None = Query(None),
):
    """List captured email leads for remarketing."""
    from app.models.visitor import EmailLead

    since = datetime.utcnow() - timedelta(days=days)
    subq = select(Doorway.id).join(Campaign).where(Campaign.user_id == current_user.id)
    if campaign_id:
        subq = subq.where(Doorway.campaign_id == campaign_id)
    subq = subq.scalar_subquery()
    r = await db.execute(
        select(EmailLead)
        .where(EmailLead.doorway_id.in_(subq), EmailLead.created_at >= since)
        .order_by(EmailLead.created_at.desc())
        .limit(2000)
    )
    leads = r.scalars().all()
    total_r = await db.execute(
        select(func.count(EmailLead.id)).where(
            EmailLead.doorway_id.in_(subq), EmailLead.created_at >= since
        )
    )
    total = total_r.scalar() or 0
    return {
        "total": total,
        "leads": [
            {"id": l.id, "email": l.email, "visitor_id": l.visitor_id, "doorway_id": l.doorway_id, "created_at": l.created_at.isoformat() if l.created_at else None}
            for l in leads
        ],
    }


@router.get("/visitors/export")
async def export_visitors(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    campaign_id: int | None = Query(None),
    format: str = Query("csv", description="csv or hashed_csv for hashed visitor_id"),
):
    """Export visitor_ids for retargeting (Facebook Custom Audiences, Google Customer Match)."""
    from app.models.visitor import VisitorEvent
    from fastapi.responses import StreamingResponse
    import csv
    import hashlib
    import io

    since = datetime.utcnow() - timedelta(days=days)
    subq = select(Doorway.id).join(Campaign).where(Campaign.user_id == current_user.id)
    if campaign_id:
        subq = subq.where(Doorway.campaign_id == campaign_id)
    subq = subq.scalar_subquery()
    r = await db.execute(
        select(VisitorEvent.visitor_id)
        .where(VisitorEvent.doorway_id.in_(subq), VisitorEvent.created_at >= since)
        .distinct()
    )
    visitor_ids = [row[0] for row in r.all() if row[0]]

    def gen():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["visitor_id"] if format != "hashed_csv" else ["hashed_id"])
        for vid in visitor_ids:
            if format == "hashed_csv":
                h = hashlib.sha256(vid.encode()).hexdigest()
                w.writerow([h])
            else:
                w.writerow([vid])
            yield buf.getvalue()
            buf.truncate(0)
            buf.seek(0)

    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=visitors_export.csv"},
    )


@router.get("/visitors")
async def get_visitors(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
    campaign_id: int | None = Query(None),
):
    """List captured visitors (for remarketing base). Requires visitor_capture_enabled."""
    from app.models.visitor import VisitorEvent
    from sqlalchemy import distinct

    since = datetime.utcnow() - timedelta(days=days)
    subq = select(Doorway.id).join(Campaign).where(Campaign.user_id == current_user.id)
    if campaign_id:
        subq = subq.where(Doorway.campaign_id == campaign_id)
    subq = subq.scalar_subquery()
    q = (
        select(
            VisitorEvent.visitor_id,
            func.count(VisitorEvent.id).label("events"),
            func.max(VisitorEvent.created_at).label("last_seen"),
        )
        .where(
            VisitorEvent.doorway_id.in_(subq),
            VisitorEvent.created_at >= since,
        )
        .group_by(VisitorEvent.visitor_id)
        .order_by(func.max(VisitorEvent.created_at).desc())
        .limit(500)
    )
    r = await db.execute(q)
    rows = r.all()
    total = await db.execute(
        select(func.count(distinct(VisitorEvent.visitor_id))).where(
            VisitorEvent.doorway_id.in_(subq),
            VisitorEvent.created_at >= since,
        )
    )
    total_count = total.scalar() or 0
    return {
        "total": total_count,
        "visitors": [
            {"visitor_id": row.visitor_id, "events": row.events, "last_seen": row.last_seen.isoformat() if row.last_seen else None}
            for row in rows
        ],
    }


@router.get("/cwv")
async def get_core_web_vitals(
    current_user: CurrentUser,
    url: str = Query(..., description="Full URL of the page to analyze"),
):
    """
    Core Web Vitals via PageSpeed Insights API (Lab data).
    Returns LCP, CLS, INP. Rate limited by Google (no key: ~25k/day).
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                params={"url": url, "strategy": "mobile", "category": "performance"},
            )
            r.raise_for_status()
            data = r.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"PageSpeed API error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    loading = data.get("loadingExperience", {}) or {}
    metrics = loading.get("metrics", {}) or {}
    result = {}
    key_map = [
        ("lcp", ["LARGEST_CONTENTFUL_PAINT_MS"]),
        ("cls", ["CUMULATIVE_LAYOUT_SHIFT_SCORE", "CUMULATIVE_LAYOUT_SHIFT_MS"]),
        ("inp", ["INTERACTION_TO_NEXT_PAINT"]),
        ("fcp", ["FIRST_CONTENTFUL_PAINT_MS"]),
    ]
    for name, key_list in key_map:
        m = next((metrics.get(k) for k in key_list if metrics.get(k)), None)
        if m and isinstance(m, dict):
            result[name] = {"percentile": m.get("percentile"), "category": m.get("category")}
    return {"url": url, "cwv": result, "loadingExperience": loading}


async def _get_min_clicks_for_profit(db: AsyncSession, user_id: int) -> int:
    r = await db.execute(select(Setting).where(Setting.user_id == user_id, Setting.key == "min_clicks_for_profit"))
    s = r.scalar_one_or_none()
    if not s or not s.value:
        return 20
    try:
        return max(1, int(s.value))
    except (TypeError, ValueError):
        return 20


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    since = datetime.utcnow() - timedelta(days=days)
    min_clicks = await _get_min_clicks_for_profit(db, current_user.id)  # порог из настроек (по умолчанию 20)
    subq = select(Doorway.id).join(Campaign).where(Campaign.user_id == current_user.id)
    r = await db.execute(
        select(
            func.coalesce(func.sum(DoorwayMetrics.impressions), 0).label("impressions"),
            func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clicks"),
            func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conversions"),
            func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("revenue"),
        ).select_from(DoorwayMetrics).where(
            DoorwayMetrics.doorway_id.in_(subq),
            DoorwayMetrics.date >= since,
        )
    )
    row = r.first()
    r2 = await db.execute(select(func.count(Doorway.id)).join(Campaign).where(Campaign.user_id == current_user.id))
    count = r2.scalar() or 0
    imp = int(row.impressions) if row else 0
    clk = int(row.clicks) if row else 0
    conv = int(row.conversions) if row else 0
    rev = float(row.revenue) if row and row.revenue is not None else 0
    ctr = (clk / imp * 100) if imp else 0
    cr = (conv / clk * 100) if clk else 0

    # Доля прибыльных дорвеев: среди дорвеев с трафиком (>= MIN_CLICKS) за период — сколько с revenue > 0
    r_profit = await db.execute(
        select(
            DoorwayMetrics.doorway_id,
            func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clk"),
            func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("rev"),
        )
        .select_from(DoorwayMetrics)
        .where(DoorwayMetrics.doorway_id.in_(subq), DoorwayMetrics.date >= since)
        .group_by(DoorwayMetrics.doorway_id)
    )
    with_traffic = [x for x in r_profit.all() if (x.clk or 0) >= min_clicks]
    profitable = [x for x in with_traffic if (x.rev or 0) > 0]
    doorways_with_traffic = len(with_traffic)
    profitable_count = len(profitable)
    profitable_pct = (
        round(profitable_count / doorways_with_traffic * 100, 1) if doorways_with_traffic else 0.0
    )

    return AnalyticsSummary(
        total_impressions=imp,
        total_clicks=clk,
        total_conversions=conv,
        total_revenue=rev,
        doorway_count=count,
        ctr_percent=round(ctr, 2),
        cr_percent=round(cr, 2),
        profitable_doorways_percent=profitable_pct,
        profitable_doorways_count=profitable_count,
        doorways_with_traffic_count=doorways_with_traffic,
    )


@router.get("/daily", response_model=AnalyticsDailyResponse)
async def get_analytics_daily(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Time series of impressions, clicks, conversions, revenue by day (for charts)."""
    since = datetime.utcnow() - timedelta(days=days)
    subq = select(Doorway.id).join(Campaign).where(Campaign.user_id == current_user.id)
    day_col = func.date_trunc("day", DoorwayMetrics.date)
    q = (
        select(
            day_col.label("day"),
            func.coalesce(func.sum(DoorwayMetrics.impressions), 0).label("impressions"),
            func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clicks"),
            func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conversions"),
            func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("revenue"),
        )
        .select_from(DoorwayMetrics)
        .where(DoorwayMetrics.doorway_id.in_(subq), DoorwayMetrics.date >= since)
        .group_by(day_col)
        .order_by(day_col)
    )
    r = await db.execute(q)
    rows = r.all()
    series = []
    for row in rows:
        day_val = row.day
        if hasattr(day_val, "strftime"):
            date_str = day_val.strftime("%Y-%m-%d")
        else:
            date_str = str(day_val)[:10]
        imp = int(row.impressions or 0)
        clk = int(row.clicks or 0)
        conv = int(row.conversions or 0)
        rev = float(row.revenue or 0)
        ctr = (clk / imp * 100) if imp else 0
        cr = (conv / clk * 100) if clk else 0
        series.append(
            DailyMetricsPoint(
                date=date_str,
                impressions=imp,
                clicks=clk,
                conversions=conv,
                revenue=rev,
                ctr_percent=round(ctr, 2),
                cr_percent=round(cr, 2),
            )
        )
    return AnalyticsDailyResponse(series=series)


@router.get("/campaigns", response_model=AnalyticsCampaignsResponse)
async def get_analytics_campaigns(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Per-campaign performance: impressions, clicks, CR, revenue, ROI."""
    since = datetime.utcnow() - timedelta(days=days)
    q = (
        select(
            Campaign.id.label("campaign_id"),
            Campaign.name.label("name"),
            func.coalesce(func.sum(DoorwayMetrics.impressions), 0).label("impressions"),
            func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clicks"),
            func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conversions"),
            func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("revenue"),
            func.count(func.distinct(DoorwayMetrics.doorway_id)).label("doorway_count"),
        )
        .select_from(DoorwayMetrics)
        .join(Doorway, Doorway.id == DoorwayMetrics.doorway_id)
        .join(Campaign, Campaign.id == Doorway.campaign_id)
        .where(Campaign.user_id == current_user.id, DoorwayMetrics.date >= since)
        .group_by(Campaign.id, Campaign.name)
        .order_by(func.coalesce(func.sum(DoorwayMetrics.revenue), 0).desc())
    )
    r = await db.execute(q)
    rows = r.all()
    campaigns = []
    for row in rows:
        imp = int(row.impressions or 0)
        clk = int(row.clicks or 0)
        conv = int(row.conversions or 0)
        rev = float(row.revenue or 0)
        dw_count = int(row.doorway_count or 0)
        ctr = (clk / imp * 100) if imp else 0
        cr = (conv / clk * 100) if clk else 0
        roi = (rev / clk) if clk else 0
        campaigns.append(
            CampaignPerformance(
                campaign_id=row.campaign_id,
                name=row.name or f"Campaign #{row.campaign_id}",
                impressions=imp,
                clicks=clk,
                conversions=conv,
                revenue=rev,
                ctr_percent=round(ctr, 2),
                cr_percent=round(cr, 2),
                roi_per_click=round(roi, 4),
                doorway_count=dw_count,
            )
        )
    return AnalyticsCampaignsResponse(campaigns=campaigns)


def _health_score(profit_status: str, clicks: int, revenue: float, conversions: int, min_clicks: int) -> int:
    """Единый скоринг здоровья дорвея 0–100."""
    if profit_status == "no_traffic":
        return min(25, 5 + (clicks * 2) if clicks else 0)  # чуть выше если есть хоть какие-то клики
    if profit_status == "unprofitable":
        return 25 + min(25, int(clicks / max(min_clicks, 1) * 5))  # 25–50
    # profitable
    rev_per_click = revenue / clicks if clicks else 0
    bonus = min(40, int(rev_per_click * 20))
    return 60 + bonus  # 60–100


def _profit_probability(profit_status: str, clicks: int, revenue: float, min_clicks: int) -> str:
    """Прогноз вероятности прибыли: low / medium / high по метрикам за период."""
    if profit_status == "profitable":
        return "high"
    if profit_status == "unprofitable":
        return "low"
    # no_traffic
    if clicks >= min_clicks // 2 and clicks < min_clicks:
        return "medium"  # есть трафик, но мало для вывода — может выйти в плюс
    if clicks > 0:
        return "medium"
    return "low"


@router.get("/doorways-metrics", response_model=AnalyticsDoorwaysMetricsResponse)
async def get_analytics_doorways_metrics(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Метрики по каждому дорвею: клики, выручка, profit_status, health_score, profit_probability, бенчмарк по кампании."""
    since = datetime.utcnow() - timedelta(days=days)
    min_clicks = await _get_min_clicks_for_profit(db, current_user.id)
    subq = select(Doorway.id, Doorway.campaign_id).join(Campaign).where(Campaign.user_id == current_user.id)
    r = await db.execute(
        select(
            DoorwayMetrics.doorway_id,
            func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clk"),
            func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("rev"),
            func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conv"),
        )
        .select_from(DoorwayMetrics)
        .where(DoorwayMetrics.doorway_id.in_(select(Doorway.id).join(Campaign).where(Campaign.user_id == current_user.id)), DoorwayMetrics.date >= since)
        .group_by(DoorwayMetrics.doorway_id)
    )
    rows = r.all()
    # Все дорвеи пользователя с campaign_id
    all_dw = await db.execute(subq)
    dw_list = all_dw.all()  # (id, campaign_id)
    dw_ids = {row[0] for row in dw_list}
    dw_to_campaign = {row[0]: row[1] for row in dw_list}

    # Бенчмарки по кампании: средний CR и ROI среди дорвеев с трафиком (>= min_clicks)
    campaign_stats: dict[int, list[tuple[int, float, int]]] = {}  # campaign_id -> [(clk, rev, conv), ...]
    for dw_id in dw_ids:
        row = next((r for r in rows if r.doorway_id == dw_id), None)
        clk = int(row.clk) if row else 0
        rev = float(row.rev) if row else 0.0
        conv = int(row.conv) if row else 0
        cid = dw_to_campaign.get(dw_id)
        if cid is None:
            continue
        if clk >= min_clicks:
            campaign_stats.setdefault(cid, []).append((clk, rev, conv))
    benchmarks: dict[int, tuple[float, float]] = {}  # campaign_id -> (avg_cr, avg_roi)
    for cid, stats in campaign_stats.items():
        total_clk = sum(s[0] for s in stats)
        total_conv = sum(s[2] for s in stats)
        total_rev = sum(s[1] for s in stats)
        if total_clk:
            benchmarks[cid] = (
                round(total_conv / total_clk * 100, 2),
                round(total_rev / total_clk, 4),
            )

    result = []
    for dw_id in dw_ids:
        row = next((r for r in rows if r.doorway_id == dw_id), None)
        clk = int(row.clk) if row else 0
        rev = float(row.rev) if row else 0.0
        conv = int(row.conv) if row else 0
        cid = dw_to_campaign.get(dw_id)
        if clk < min_clicks:
            status = "no_traffic"
        elif rev > 0:
            status = "profitable"
        else:
            status = "unprofitable"
        health = _health_score(status, clk, rev, conv, min_clicks)
        prob = _profit_probability(status, clk, rev, min_clicks)
        b = benchmarks.get(cid)
        bench_cr, bench_roi = (b[0], b[1]) if b else (None, None)
        my_cr = (conv / clk * 100) if clk else 0
        my_roi = (rev / clk) if clk else 0
        above_cr = (my_cr > bench_cr) if bench_cr is not None and clk >= min_clicks else None
        above_roi = (my_roi > bench_roi) if bench_roi is not None and clk >= min_clicks else None
        result.append(
            DoorwayProfitMetric(
                doorway_id=dw_id,
                clicks=clk,
                revenue=round(rev, 2),
                conversions=conv,
                profit_status=status,
                health_score=min(100, health),
                min_clicks_used=min_clicks,
                profit_probability=prob,
                campaign_id=cid,
                benchmark_cr=bench_cr,
                benchmark_roi=bench_roi,
                above_benchmark_cr=above_cr,
                above_benchmark_roi=above_roi,
            )
        )
    return AnalyticsDoorwaysMetricsResponse(doorways=result, min_clicks_used=min_clicks)
