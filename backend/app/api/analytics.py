"""Analytics API: metrics, postback, summary."""

import json
from datetime import datetime, timedelta
from typing import List
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, quote, quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
from app.models.offer import Offer
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
    EarlyDoorwayItem,
    EarlyDoorwaysResponse,
)

router = APIRouter()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host or ""
    return ""


def _device_from_ua(user_agent: str) -> str:
    if not user_agent:
        return "—"
    ua = user_agent.lower()
    if ("mobile" in ua and "ipad" not in ua) or ("android" in ua and "mobile" in ua):
        return "mobile"
    if "tablet" in ua or "ipad" in ua:
        return "tablet"
    return "desktop"


async def _country_from_ip(ip: str) -> str | None:
    if not ip or ip.startswith("127.") or ip == "::1" or ip.startswith("10.") or ip.startswith("192.168.") or ip.startswith("172."):
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"http://ip-api.com/json/{ip}?fields=countryCode")
            if r.status_code == 200:
                data = r.json()
                return data.get("countryCode") or None
    except Exception:
        pass
    return None


def _ip_display(ip: str) -> str:
    if not ip:
        return "—"
    parts = ip.replace(":", ".").split(".")
    if len(parts) >= 4:
        return ".".join(["*"] * (len(parts) - 2) + parts[-2:])
    return "***"


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
    Postback from affiliate network. sub_id = doorway_id or doorway_id_offer_id (for per-offer metrics).
    GET: ?sub_id=123&payout=10.5  or  ?sub_id=123_45&payout=10.5 (offer 45).
    Bot filter: rejects if > 20 postbacks/min per doorway.
    """
    offer_id = None
    traffic_source = None
    try:
        raw = (sub_id or "").strip()
        if "_" in raw:
            parts = raw.split("_")
            doorway_id = int(parts[0] or "0")
            if len(parts) >= 2 and parts[1].isdigit():
                offer_id = int(parts[1])
                traffic_source = parts[2] if len(parts) > 2 else None
            else:
                traffic_source = parts[1] if len(parts) >= 2 else None
        else:
            doorway_id = int(raw or "0")
    except (ValueError, IndexError):
        return {"status": "ignored", "reason": "invalid sub_id"}
    if traffic_source is not None:
        import re
        traffic_source = re.sub(r"[^a-z0-9_-]", "", (traffic_source or "").lower())[:32] or None
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
    if offer_id and offer_id > 0:
        from app.models.offer_metrics import OfferMetrics
        from app.models.offer import Offer
        r_offer = await db.execute(select(Offer).where(Offer.id == offer_id, Offer.campaign_id == dw.campaign_id))
        if r_offer.scalar_one_or_none():
            r3 = await db.execute(
                select(OfferMetrics).where(
                    OfferMetrics.offer_id == offer_id,
                    OfferMetrics.date >= today,
                    OfferMetrics.date < tomorrow,
                )
            )
            om = r3.scalar_one_or_none()
            if om:
                om.conversions += 1
                om.revenue += payout or 0
            else:
                om = OfferMetrics(offer_id=offer_id, date=today, conversions=1, revenue=payout or 0)
                db.add(om)
    if traffic_source and len(traffic_source) <= 32:
        from app.models.doorway_source_metrics import DoorwaySourceMetrics
        r_src = await db.execute(
            select(DoorwaySourceMetrics).where(
                DoorwaySourceMetrics.doorway_id == doorway_id,
                DoorwaySourceMetrics.date >= today,
                DoorwaySourceMetrics.date < tomorrow,
                DoorwaySourceMetrics.source == traffic_source,
            )
        )
        sm = r_src.scalar_one_or_none()
        if sm:
            sm.conversions += 1
            sm.revenue += payout or 0
        else:
            sm = DoorwaySourceMetrics(
                doorway_id=doorway_id,
                date=today,
                source=traffic_source,
                conversions=1,
                revenue=payout or 0,
            )
            db.add(sm)
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
    request: Request,
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
            ip = _client_ip(request)
            ua = request.headers.get("user-agent") or ""
            meta = {"ip": ip, "user_agent": ua[:500], "device": _device_from_ua(ua)}
            country = await _country_from_ip(ip)
            if country:
                meta["country"] = country
            ev = VisitorEvent(visitor_id=vid, doorway_id=dw, campaign_id=door.campaign_id, event_type="visit", meta=meta)
            db.add(ev)
            await db.commit()
    return Response(content=_PIXEL_GIF, media_type="image/gif")


@router.get("/click")
async def click_redirect(
    dw: int = Query(..., alias="dw", description="doorway_id"),
    vid: str | None = Query(None, alias="vid", description="visitor_id for remarketing"),
    geo: str | None = Query(None, description="Country code for GEO offer routing"),
    device: str | None = Query(None, description="mobile|desktop for device offer routing"),
    oid: int | None = Query(None, alias="oid", description="offer_id when link was built with offer (for ROI metrics)"),
    utm_source: str | None = Query(None, alias="utm_source", description="Traffic source for ROI by source (e.g. google, fb)"),
    src: str | None = Query(None, alias="src", description="Alias for utm_source"),
    db: AsyncSession = Depends(get_db),
):
    """
    Click tracking: redirect to affiliate URL with sub_id (doorway_id or doorway_id_offer_id or + _source).
    Increment DoorwayMetrics.clicks, OfferMetrics.clicks when oid present, DoorwaySourceMetrics when utm_source present.
    """
    import re
    raw_source = (utm_source or src or "").strip().lower()
    traffic_source = None
    if raw_source:
        traffic_source = re.sub(r"[^a-z0-9_-]", "", raw_source)[:32] or None
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
    from app.services.deploy import _append_sub_id, get_best_offer_url_by_roi, _get_best_offer_url
    off_r = await db.execute(
        select(Offer)
        .where(Offer.campaign_id == camp.id, Offer.is_active == True)
        .order_by(Offer.priority.desc())
    )
    offers_list = [{"id": o.id, "url": o.url, "geo": o.geo, "device": o.device, "priority": o.priority, "is_active": o.is_active, "rate": o.rate} for o in off_r.scalars().all()]
    chosen_offer_id = oid
    if offers_list:
        # Если в ссылке передан oid — берём URL именно этого оффера
        if chosen_offer_id:
            for o in offers_list:
                if o.get("id") == chosen_offer_id and o.get("url"):
                    aff_url = o["url"]
                    break
        if not aff_url or aff_url == camp.affiliate_url:
            best_url, best_oid = await get_best_offer_url_by_roi(db, offers_list, geo=geo, device=device)
            if best_url:
                aff_url = best_url
                if chosen_offer_id is None:
                    chosen_offer_id = best_oid
            else:
                # Нет ROI — выбираем по приоритету/geo/device, ссылка всегда из оффера
                fallback_url = _get_best_offer_url(offers_list, geo=geo, device=device)
                if fallback_url:
                    aff_url = fallback_url
                    if chosen_offer_id is None:
                        chosen_offer_id = next((o["id"] for o in offers_list if o.get("url") == fallback_url), None)
    target = _append_sub_id(aff_url, doorway_id, chosen_offer_id, traffic_source)
    # Плейсхолдеры для партнёрских сетей (Zeydoo и др.): {SOURCE_ID} = sub_id, {CLICK_ID} = vid
    sid = f"{doorway_id}_{chosen_offer_id}" if (chosen_offer_id and chosen_offer_id > 0) else str(doorway_id)
    if traffic_source:
        sid = f"{sid}_{traffic_source}"
    if "{SOURCE_ID}" in target:
        target = target.replace("{SOURCE_ID}", sid)
    if "{CLICK_ID}" in target:
        target = target.replace("{CLICK_ID}", (vid or ""))
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
    if chosen_offer_id and chosen_offer_id > 0:
        from app.models.offer_metrics import OfferMetrics
        tomorrow = today + timedelta(days=1)
        r3 = await db.execute(
            select(OfferMetrics).where(
                OfferMetrics.offer_id == chosen_offer_id,
                OfferMetrics.date >= today,
                OfferMetrics.date < tomorrow,
            )
        )
        om = r3.scalar_one_or_none()
        if om:
            om.clicks = (om.clicks or 0) + 1
        else:
            om = OfferMetrics(offer_id=chosen_offer_id, date=today, clicks=1)
            db.add(om)
    if traffic_source:
        from app.models.doorway_source_metrics import DoorwaySourceMetrics
        tomorrow = today + timedelta(days=1)
        r_src = await db.execute(
            select(DoorwaySourceMetrics).where(
                DoorwaySourceMetrics.doorway_id == doorway_id,
                DoorwaySourceMetrics.date >= today,
                DoorwaySourceMetrics.date < tomorrow,
                DoorwaySourceMetrics.source == traffic_source,
            )
        )
        sm = r_src.scalar_one_or_none()
        if sm:
            sm.clicks = (sm.clicks or 0) + 1
        else:
            sm = DoorwaySourceMetrics(doorway_id=doorway_id, date=today, source=traffic_source, clicks=1)
            db.add(sm)
    if vid and len(vid) <= 64 and vid.replace("-", "").replace("_", "").isalnum():
        from app.models.visitor import VisitorEvent
        ev = VisitorEvent(
            visitor_id=vid, doorway_id=doorway_id, campaign_id=camp.id,
            event_type="click", meta={"geo": geo, "device": device, "offer_id": chosen_offer_id},
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
    request: Request,
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
    ip = _client_ip(request)
    ua = request.headers.get("user-agent") or ""
    meta = {"ip": ip, "user_agent": ua[:500], "device": _device_from_ua(ua)}
    country = await _country_from_ip(ip)
    if country:
        meta["country"] = country
    ev = VisitorEvent(
        visitor_id=data.visitor_id,
        doorway_id=data.doorway_id,
        campaign_id=dw.campaign_id,
        event_type="push_subscribe",
        meta=meta,
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


@router.get("/track-and-redirect")
async def track_and_redirect(
    request: Request,
    vid: str = Query(..., description="visitor_id"),
    to: str = Query(..., description="URL to redirect to"),
    dw: int = Query(..., description="doorway_id"),
    db: AsyncSession = Depends(get_db),
):
    """Пинг: по ссылке из push записываем IP/UA/device/country визитора и редиректим на to. Без авторизации."""
    from app.models.visitor import VisitorEvent

    if len(vid) > 64 or not vid.replace("-", "").replace("_", "").replace(".", "").isalnum():
        raise HTTPException(400, "Invalid visitor_id")
    r = await db.execute(select(Doorway).where(Doorway.id == dw))
    door = r.scalar_one_or_none()
    if not door:
        raise HTTPException(404, "Doorway not found")
    ip = _client_ip(request)
    ua = request.headers.get("user-agent") or ""
    meta = {"ip": ip, "user_agent": ua[:500], "device": _device_from_ua(ua)}
    country = await _country_from_ip(ip)
    if country:
        meta["country"] = country
    ev = VisitorEvent(
        visitor_id=vid,
        doorway_id=dw,
        campaign_id=door.campaign_id,
        event_type="visit",
        meta=meta,
    )
    db.add(ev)
    await db.commit()
    return RedirectResponse(url=to, status_code=302)


class SendPushRequest(BaseModel):
    campaign_id: int | None = None
    doorway_id: int | None = None
    title: str
    body: str
    url: str | None = None
    use_best_offer_url: bool = False


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
    # Ретаргетинг: ссылка на лучший оффер по ROI
    push_url = data.url
    if (not push_url or not push_url.strip()) and data.use_best_offer_url and (data.campaign_id or data.doorway_id):
        from app.services.deploy import get_best_offer_url_by_roi, _append_sub_id
        camp_id = data.campaign_id
        if data.doorway_id:
            r_c = await db.execute(select(Doorway.campaign_id).where(Doorway.id == data.doorway_id))
            camp_id = r_c.scalar_one_or_none()
        if camp_id:
            off_r = await db.execute(
                select(Offer).where(Offer.campaign_id == camp_id, Offer.is_active == True).order_by(Offer.priority.desc())
            )
            offers_raw = off_r.scalars().all()
            offers_list = [{"id": o.id, "url": o.url, "geo": o.geo, "device": o.device, "priority": o.priority, "is_active": o.is_active, "rate": o.rate} for o in offers_raw]
            if offers_list:
                best_url, best_oid = await get_best_offer_url_by_roi(db, offers_list, None, None)
                dw_id = subs[0].doorway_id if subs else None
                if best_url and dw_id:
                    set_base = await db.execute(
                        select(Setting).where(
                            Setting.user_id == current_user.id,
                            Setting.key.in_(["api_base_url", "click_tracking_enabled"]),
                        )
                    )
                    settings_map = {s.key: s.value for s in set_base.scalars().all()}
                    click_base = (settings_map.get("api_base_url") or "").strip().rstrip("/")
                    click_enabled = str(settings_map.get("click_tracking_enabled") or "").lower() == "true"
                    if click_enabled and click_base:
                        push_url = f"{click_base}/api/analytics/click?dw={dw_id}&oid={best_oid or ''}"
                    else:
                        push_url = _append_sub_id(best_url, dw_id, best_oid)
    if not push_url or not push_url.strip():
        push_url = "/"
    set_r = await db.execute(
        select(Setting).where(
            Setting.user_id == current_user.id,
            Setting.key.in_(["vapid_private_key", "api_base_url"]),
        )
    )
    settings_list = set_r.scalars().all()
    settings_map = {s.key: s.value for s in settings_list}
    vapid_priv = settings_map.get("vapid_private_key")
    if not vapid_priv:
        raise HTTPException(400, "VAPID ключи не настроены. Сгенерируйте в Настройках.")
    api_base_url = (settings_map.get("api_base_url") or "").strip().rstrip("/") if settings_map.get("api_base_url") else ""
    try:
        from pywebpush import webpush
    except ImportError:
        raise HTTPException(503, "pywebpush не установлен")
    vapid_claims = {"sub": "mailto:admin@dorvey.local"}

    def _send_one(sub_info: dict, url: str) -> bool:
        try:
            payload = {"title": data.title, "body": data.body, "url": url or "/"}
            webpush(
                subscription_info=sub_info,
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=vapid_priv,
                vapid_claims=vapid_claims,
            )
            return True
        except Exception:
            return False

    sent = 0
    for s in subs:
        if api_base_url:
            link_url = f"{api_base_url}/api/analytics/track-and-redirect?vid={quote(s.visitor_id)}&to={quote(push_url)}&dw={s.doorway_id}"
        else:
            link_url = push_url
        ok = await asyncio.to_thread(_send_one, s.subscription, link_url)
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
    from sqlalchemy import distinct, tuple_

    since = datetime.utcnow() - timedelta(days=days)
    subq = select(Doorway.id).join(Campaign).where(Campaign.user_id == current_user.id)
    if campaign_id:
        subq = subq.where(Doorway.campaign_id == campaign_id)
    subq = subq.scalar_subquery()
    q = (
        select(
            VisitorEvent.visitor_id,
            func.count(VisitorEvent.id).label("events"),
            func.min(VisitorEvent.created_at).label("first_seen"),
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

    visitors_list = [
        {
            "visitor_id": row.visitor_id,
            "events": row.events,
            "first_seen": row.first_seen.isoformat() if row.first_seen else None,
            "last_seen": row.last_seen.isoformat() if row.last_seen else None,
        }
        for row in rows
    ]
    if visitors_list:
        vids = [v["visitor_id"] for v in visitors_list]
        q_extra = select(VisitorEvent.visitor_id, VisitorEvent.doorway_id, VisitorEvent.event_type).where(
            VisitorEvent.visitor_id.in_(vids),
            VisitorEvent.doorway_id.in_(subq),
        )
        r_extra = await db.execute(q_extra)
        visitor_doorway_ids = {}
        visitor_event_counts = {}
        for row in r_extra.all():
            vid = row.visitor_id
            visitor_doorway_ids.setdefault(vid, set()).add(row.doorway_id)
            visitor_event_counts.setdefault(vid, {}).setdefault(row.event_type, 0)
            visitor_event_counts[vid][row.event_type] += 1
        all_dw_ids = list({dw_id for s in visitor_doorway_ids.values() for dw_id in s})
        doorways_path_map = {}
        if all_dw_ids:
            rd_all = await db.execute(select(Doorway.id, Doorway.path, Doorway.title).where(Doorway.id.in_(all_dw_ids)))
            for d in rd_all.all():
                doorways_path_map[d.id] = (d.title or (d.path if d.path else "") or "").strip() or str(d.path or "")
        for v in visitors_list:
            dw_ids = visitor_doorway_ids.get(v["visitor_id"]) or set()
            v["doorways_visited"] = [doorways_path_map.get(i, str(i)) for i in sorted(dw_ids)]
            counts = visitor_event_counts.get(v["visitor_id"]) or {}
            parts = []
            if counts.get("visit"):
                parts.append(f"{counts['visit']} визит(ов)")
            if counts.get("click"):
                parts.append(f"{counts['click']} клик(ов)")
            if counts.get("push_subscribe"):
                parts.append(f"{counts['push_subscribe']} подписка(ок)")
            v["events_breakdown"] = ", ".join(parts) if parts else "—"

        pairs = [(row.visitor_id, row.last_seen) for row in rows if row.last_seen]
        if pairs:
            q2 = select(VisitorEvent.visitor_id, VisitorEvent.created_at, VisitorEvent.doorway_id, VisitorEvent.campaign_id, VisitorEvent.meta).where(
                tuple_(VisitorEvent.visitor_id, VisitorEvent.created_at).in_(pairs),
                VisitorEvent.doorway_id.in_(subq),
            )
            r2 = await db.execute(q2)
            last_events = {}
            for row in r2.all():
                k = (row.visitor_id, row.created_at.isoformat() if row.created_at else None)
                last_events[k] = (row.doorway_id, row.campaign_id, row.meta or {})
            dw_ids = list({x[0] for x in last_events.values()})
            camp_ids = list({x[1] for x in last_events.values()})
            doorways_map = {}
            campaigns_map = {}
            if dw_ids:
                rd = await db.execute(select(Doorway.id, Doorway.path, Doorway.title).where(Doorway.id.in_(dw_ids)))
                for d in rd.all():
                    doorways_map[d.id] = (d.title or (d.path if d.path else "") or "").strip() or str(d.path or "")
            if camp_ids:
                rc = await db.execute(select(Campaign.id, Campaign.name).where(Campaign.id.in_(camp_ids)))
                for c in rc.all():
                    campaigns_map[c.id] = c.name or ""
            for v in visitors_list:
                key = (v["visitor_id"], v["last_seen"])
                row_data = last_events.get(key)
                if row_data:
                    de_dw, de_camp, meta = row_data[0], row_data[1], row_data[2]
                    v["doorway_id"] = de_dw
                    v["campaign_id"] = de_camp
                    v["doorway_path"] = doorways_map.get(de_dw, "")
                    v["campaign_name"] = campaigns_map.get(de_camp, "")
                    v["country"] = meta.get("country") or None
                    v["device"] = meta.get("device") or None
                    v["ip"] = _ip_display(meta.get("ip") or "")

    return {
        "total": total_count,
        "visitors": visitors_list,
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

    external_by_country = None
    enabled, news_key, gnews_key, mstack_key, guard_key, season_url = await _load_external_settings(db, current_user.id)
    any_news = news_key or gnews_key or mstack_key or guard_key
    if enabled and (any_news or season_url):
        geo_r = await db.execute(
            select(Offer.geo).join(Campaign).where(Campaign.user_id == current_user.id, Offer.geo.isnot(None), Offer.geo != "")
        )
        geos = list({r[0].lower()[:2] for r in geo_r.all() if r[0]})[:20]
        if geos:
            from app.services.external_data_service import get_external_signals as fetch_signals
            external_by_country = {}
            for g in geos:
                external_by_country[g] = await fetch_signals(
                    country_code=g, days=days,
                    news_api_key=news_key, gnews_api_key=gnews_key,
                    mediastack_api_key=mstack_key, guardian_api_key=guard_key,
                    seasonality_data_url=season_url,
                )
    return AnalyticsDoorwaysMetricsResponse(doorways=result, min_clicks_used=min_clicks, external_signals_by_country=external_by_country)


@router.get("/early-doorways", response_model=EarlyDoorwaysResponse)
async def get_early_doorways(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(3, ge=1, le=14, description="Дорвеи задеплоены за последние N дней"),
    min_clicks: int = Query(20, ge=5, le=200, description="Минимум кликов для попадания в список"),
):
    """
    Дорвеи, задеплоенные за последние N дней, у которых есть трафик (>= min_clicks), но 0 конверсий.
    Для быстрого реагирования на 2–3 день: сменить оффер или поставить на паузу.
    """
    since = datetime.utcnow() - timedelta(days=days)
    r = await db.execute(
        select(Doorway.id, Doorway.campaign_id, Doorway.title, Doorway.deployed_at)
        .join(Campaign)
        .where(
            Campaign.user_id == current_user.id,
            Doorway.status.in_(["deployed", "indexed"]),
            Doorway.deployed_at.isnot(None),
            Doorway.deployed_at >= since,
        )
    )
    doorways = r.all()
    if not doorways:
        return EarlyDoorwaysResponse(doorways=[], days=days, min_clicks=min_clicks)
    dw_ids = [row[0] for row in doorways]
    r2 = await db.execute(
        select(
            DoorwayMetrics.doorway_id,
            func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clk"),
            func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conv"),
            func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("rev"),
        )
        .where(
            DoorwayMetrics.doorway_id.in_(dw_ids),
            DoorwayMetrics.date >= since,
        )
        .group_by(DoorwayMetrics.doorway_id)
    )
    metrics = {row.doorway_id: (int(row.clk or 0), int(row.conv or 0), float(row.rev or 0)) for row in r2.all()}
    result_list = []
    for dw_id, camp_id, title, deployed_at in doorways:
        clk, conv, rev = metrics.get(dw_id, (0, 0, 0.0))
        if clk < min_clicks or conv > 0 or rev > 0:
            continue
        result_list.append(
            EarlyDoorwayItem(
                doorway_id=dw_id,
                campaign_id=camp_id,
                title=title,
                clicks=clk,
                conversions=conv,
                revenue=rev,
                deployed_at=deployed_at,
            )
        )
    return EarlyDoorwaysResponse(doorways=result_list, days=days, min_clicks=min_clicks)


@router.get("/doorway/{doorway_id}/profit-forecast")
async def get_doorway_profit_forecast(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(7, ge=1, le=30),
):
    """
    Прогноз «выйдет в плюс»: при текущем трафике и бенчмарке кампании — через сколько дней дорвей выйдет на прибыль.
    """
    r = await db.execute(
        select(Doorway, Campaign.id)
        .join(Campaign)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    row = r.first()
    if not row:
        raise HTTPException(404, "Doorway not found")
    dw, camp_id = row
    since = datetime.utcnow() - timedelta(days=days)
    m = await db.execute(
        select(
            func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clk"),
            func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conv"),
            func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("rev"),
        )
        .where(DoorwayMetrics.doorway_id == doorway_id, DoorwayMetrics.date >= since)
    )
    mm = m.first()
    clk = int(mm.clk or 0)
    conv = int(mm.conv or 0)
    rev = float(mm.rev or 0)
    min_clicks = await _get_min_clicks_for_profit(db, current_user.id)
    # Бенчмарк по кампании
    subq = select(Doorway.id).where(Doorway.campaign_id == camp_id)
    br = await db.execute(
        select(
            func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("c"),
            func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("r"),
        )
        .where(DoorwayMetrics.doorway_id.in_(subq), DoorwayMetrics.date >= since)
    )
    brr = br.first()
    total_clk = int(brr.c or 0)
    total_rev = float(brr.r or 0)
    benchmark_roi = (total_rev / total_clk) if total_clk else None
    if rev > 0:
        return {
            "doorway_id": doorway_id,
            "status": "profitable",
            "days_to_profit": 0,
            "message": "Дорвей уже приносит прибыль.",
            "clicks": clk,
            "conversions": conv,
            "revenue": rev,
            "benchmark_roi": benchmark_roi,
        }
    if clk < min_clicks:
        return {
            "doorway_id": doorway_id,
            "status": "no_traffic",
            "days_to_profit": None,
            "message": f"Мало данных: нужно минимум {min_clicks} кликов за период.",
            "clicks": clk,
            "conversions": conv,
            "revenue": rev,
            "benchmark_roi": benchmark_roi,
        }
    if not benchmark_roi or benchmark_roi <= 0:
        return {
            "doorway_id": doorway_id,
            "status": "unprofitable",
            "days_to_profit": None,
            "message": "По кампании нет бенчмарка ROI для прогноза.",
            "clicks": clk,
            "conversions": conv,
            "revenue": rev,
            "benchmark_roi": benchmark_roi,
        }
    # Не в плюсе: оценка дней до выхода на benchmark_roi
    clicks_per_day = clk / days if days else 0
    if clicks_per_day <= 0:
        return {
            "doorway_id": doorway_id,
            "status": "unprofitable",
            "days_to_profit": None,
            "message": "Нет трафика за период — прогноз невозможен.",
            "clicks": clk,
            "conversions": conv,
            "revenue": rev,
            "benchmark_roi": benchmark_roi,
        }
    rev_needed = benchmark_roi * clk - rev
    rev_per_day = clicks_per_day * benchmark_roi
    if rev_per_day <= 0:
        days_to_profit = None
    else:
        days_to_profit = max(1, int(rev_needed / rev_per_day) + 1)
    return {
        "doorway_id": doorway_id,
        "status": "unprofitable",
        "days_to_profit": days_to_profit,
        "message": f"При текущем трафике (~{clicks_per_day:.0f} кл/день) выход в плюс ориентировочно через {days_to_profit} дн." if days_to_profit else "Недостаточно данных для прогноза.",
        "clicks": clk,
        "conversions": conv,
        "revenue": rev,
        "benchmark_roi": benchmark_roi,
        "clicks_per_day": round(clicks_per_day, 1),
    }


@router.get("/doorway/{doorway_id}/traffic-by-source")
async def get_doorway_traffic_by_source(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """
    Метрики по источникам трафика (utm_source) для дорвея: клики, конверсии, выручка по каждому source.
    """
    from app.models.doorway_source_metrics import DoorwaySourceMetrics

    r = await db.execute(
        select(Doorway.id, Doorway.campaign_id)
        .join(Campaign, Doorway.campaign_id == Campaign.id)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    row = r.first()
    if not row:
        raise HTTPException(404, "Doorway not found")
    since = datetime.utcnow() - timedelta(days=days)
    since = since.replace(hour=0, minute=0, second=0, microsecond=0)
    agg = await db.execute(
        select(
            DoorwaySourceMetrics.source,
            func.coalesce(func.sum(DoorwaySourceMetrics.clicks), 0).label("clicks"),
            func.coalesce(func.sum(DoorwaySourceMetrics.conversions), 0).label("conversions"),
            func.coalesce(func.sum(DoorwaySourceMetrics.revenue), 0).label("revenue"),
        )
        .where(
            DoorwaySourceMetrics.doorway_id == doorway_id,
            DoorwaySourceMetrics.date >= since,
        )
        .group_by(DoorwaySourceMetrics.source)
    )
    rows = agg.all()
    return {
        "doorway_id": doorway_id,
        "days": days,
        "sources": [
            {"source": r.source, "clicks": int(r.clicks), "conversions": int(r.conversions), "revenue": float(r.revenue)}
            for r in rows
        ],
    }


async def _load_external_settings(db: AsyncSession, user_id: int):
    """Returns (enabled, news_key, gnews_key, mediastack_key, guardian_key, season_url)."""
    r = await db.execute(
        select(Setting).where(
            Setting.user_id == user_id,
            Setting.key.in_([
                "news_api_key", "gnews_api_key", "mediastack_api_key", "guardian_api_key",
                "external_data_enabled", "seasonality_data_url",
            ]),
        )
    )
    rows = {s.key: s.value for s in r.scalars().all()}
    enabled = (rows.get("external_data_enabled") or "").strip().lower() in ("true", "1")
    news_key = (rows.get("news_api_key") or "").strip() or None
    gnews_key = (rows.get("gnews_api_key") or "").strip() or None
    mstack_key = (rows.get("mediastack_api_key") or "").strip() or None
    guard_key = (rows.get("guardian_api_key") or "").strip() or None
    season_url = (rows.get("seasonality_data_url") or "").strip() or None
    return enabled, news_key, gnews_key, mstack_key, guard_key, season_url


@router.get("/external-signals")
async def get_external_signals_endpoint(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    country: str = Query(None, description="Single country code (e.g. us, de)"),
    countries: str = Query(None, description="Comma-separated country codes for batch"),
    days: int = Query(7, ge=1, le=90, description="Period in days"),
):
    """External data signals (news, seasonality). Single country or batch. Uses Settings → Внешние данные."""
    enabled, news_key, gnews_key, mstack_key, guard_key, season_url = await _load_external_settings(db, current_user.id)
    if not enabled:
        one = {"country": (country or "us").lower()[:2], "period_days": days, "sources_used": [], "news": None, "seasonality": None}
        return {"by_country": {one["country"]: one}} if countries else one

    from app.services.external_data_service import get_external_signals as fetch_signals
    if countries:
        codes = [c.strip().lower()[:2] for c in countries.split(",") if c.strip()]
        if not codes:
            codes = ["us"]
        by_country = {}
        for c in codes:
            by_country[c] = await fetch_signals(
                country_code=c, days=days,
                news_api_key=news_key, gnews_api_key=gnews_key,
                mediastack_api_key=mstack_key, guardian_api_key=guard_key,
                seasonality_data_url=season_url,
            )
        return {"by_country": by_country, "period_days": days}
    one = await fetch_signals(
        country_code=country or "us", days=days,
        news_api_key=news_key, gnews_api_key=gnews_key,
        mediastack_api_key=mstack_key, guardian_api_key=guard_key,
        seasonality_data_url=season_url,
    )
    return one


@router.get("/offer-country-recommendations")
async def get_offer_country_recommendations(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    """Рекомендации по странам: наши клики по гео + внешние сигналы. Для выбора «какие офферы/страны брать»."""
    since = datetime.utcnow() - timedelta(days=days)
    # Гео из офферов пользователя
    geo_r = await db.execute(
        select(Offer.geo, func.count(Offer.id).label("cnt"))
        .join(Campaign)
        .where(Campaign.user_id == current_user.id, Offer.geo.isnot(None), Offer.geo != "")
        .group_by(Offer.geo)
    )
    geo_rows = geo_r.all()
    if not geo_rows:
        return {"recommendations": [], "period_days": days}

    geos = [r[0].lower()[:2] for r in geo_rows if r[0]]
    offer_count_by_geo = {r[0].lower()[:2]: r[1] for r in geo_rows if r[0]}

    # Клики по гео из VisitorEvent (event_type=click, meta->geo)
    from app.models.visitor import VisitorEvent
    recommendations = []
    for g in geos:
        geo_expr = func.lower(func.coalesce(func.jsonb_extract_path_text(VisitorEvent.meta, "geo"), ""))
        clk_r = await db.execute(
            select(func.count(VisitorEvent.id))
            .where(
                VisitorEvent.campaign_id.in_(select(Campaign.id).where(Campaign.user_id == current_user.id)),
                VisitorEvent.event_type == "click",
                VisitorEvent.created_at >= since,
                geo_expr == g,
            )
        )
        our_clicks = clk_r.scalar() or 0
        recommendations.append({"country": g, "offer_count": offer_count_by_geo.get(g, 0), "our_clicks": our_clicks})

    # Внешние сигналы
    enabled, news_key, gnews_key, mstack_key, guard_key, season_url = await _load_external_settings(db, current_user.id)
    any_news_rec = news_key or gnews_key or mstack_key or guard_key
    if enabled and (any_news_rec or season_url):
        from app.services.external_data_service import get_external_signals as fetch_signals
        for rec in recommendations:
            g = rec["country"]
            sig = await fetch_signals(
                country_code=g, days=days,
                news_api_key=news_key, gnews_api_key=gnews_key,
                mediastack_api_key=mstack_key, guardian_api_key=guard_key,
                seasonality_data_url=season_url,
            )
            rec["external_news_count"] = len(sig.get("news", {}).get("headlines") or [])
            rec["external_seasonality"] = bool(sig.get("seasonality") and "error" not in (sig.get("seasonality") or {}))
            rec["sources_used"] = sig.get("sources_used") or []
            # Приоритет: наши клики + внешние данные
            score = float(rec["our_clicks"]) * 0.02 + rec["external_news_count"] * 0.3 + (10 if rec["external_seasonality"] else 0)
            rec["priority_score"] = round(score, 1)
            rec["recommended"] = rec["offer_count"] > 0 and (rec["our_clicks"] > 0 or rec["external_news_count"] > 0 or rec["external_seasonality"])
        recommendations.sort(key=lambda x: (-(x.get("priority_score") or 0), -x["our_clicks"]))
    else:
        for rec in recommendations:
            rec["external_news_count"] = 0
            rec["external_seasonality"] = False
            rec["sources_used"] = []
            rec["priority_score"] = float(rec["our_clicks"]) * 0.02
            rec["recommended"] = rec["offer_count"] > 0 and rec["our_clicks"] > 0
        recommendations.sort(key=lambda x: (-x["our_clicks"], -x["offer_count"]))

    return {"recommendations": recommendations, "period_days": days}


@router.get("/cross-campaign-offer-suggestions")
async def get_cross_campaign_offer_suggestions(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    campaign_id: int = Query(..., description="Кампания, для которой подбираем офферы"),
    geo: str | None = Query(None, description="Фильтр по гео (RU, US, …)"),
    days: int = Query(30, ge=7, le=365),
    limit: int = Query(10, ge=1, le=50),
):
    """
    Офферы из других кампаний пользователя с хорошим ROI — подсказка «что конвертит в других кампаниях».
    """
    from app.models.offer_metrics import OfferMetrics

    ok = await db.execute(
        select(Campaign.id).where(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
    )
    if not ok.scalar_one_or_none():
        raise HTTPException(404, "Campaign not found")
    since = datetime.utcnow() - timedelta(days=days)
    # Офферы из других кампаний того же пользователя (не текущая)
    off_subq = (
        select(Offer.id, Offer.campaign_id, Offer.url, Offer.geo, Offer.name)
        .join(Campaign)
        .where(Campaign.user_id == current_user.id, Campaign.id != campaign_id, Offer.is_active == True)
    )
    if geo:
        off_subq = off_subq.where(Offer.geo.isnot(None), func.upper(Offer.geo) == geo.upper())
    r = await db.execute(off_subq)
    other_offers = r.all()
    if not other_offers:
        return {"suggestions": [], "period_days": days}
    offer_ids = [o[0] for o in other_offers]
    met = await db.execute(
        select(
            OfferMetrics.offer_id,
            func.coalesce(func.sum(OfferMetrics.clicks), 0).label("clk"),
            func.coalesce(func.sum(OfferMetrics.revenue), 0).label("rev"),
        )
        .where(OfferMetrics.offer_id.in_(offer_ids), OfferMetrics.date >= since)
        .group_by(OfferMetrics.offer_id)
    )
    metrics = {row.offer_id: (int(row.clk or 0), float(row.rev or 0)) for row in met.all()}
    suggestions = []
    for oid, camp_id, url, ogeo, name in other_offers:
        clk, rev = metrics.get(oid, (0, 0))
        if clk < 5:
            continue
        roi = rev / clk if clk else 0
        suggestions.append({
            "offer_id": oid,
            "campaign_id": camp_id,
            "url": url,
            "geo": ogeo,
            "name": name,
            "clicks": clk,
            "revenue": round(rev, 2),
            "roi_per_click": round(roi, 4),
        })
    suggestions.sort(key=lambda x: -x["roi_per_click"])
    return {"suggestions": suggestions[:limit], "period_days": days}
