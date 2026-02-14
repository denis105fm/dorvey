"""Analytics API: metrics, postback, summary."""

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
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
    """
    try:
        doorway_id = int(sub_id or "0")
    except ValueError:
        return {"status": "ignored", "reason": "invalid sub_id"}
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


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
):
    since = datetime.utcnow() - timedelta(days=days)
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
    return AnalyticsSummary(
        total_impressions=int(row.impressions) if row else 0,
        total_clicks=int(row.clicks) if row else 0,
        total_conversions=int(row.conversions) if row else 0,
        total_revenue=float(row.revenue) if row else 0,
        doorway_count=count,
    )
