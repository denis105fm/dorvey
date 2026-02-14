"""Cron endpoints - auto-rollback, auto-switch offers, health checks. Call via external cron."""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.doorway import Doorway, DoorwayMetrics, DoorwayVersion
from app.models.campaign import Campaign
from app.models.offer import Offer

router = APIRouter()


@router.post("/auto-rollback")
async def auto_rollback(
    threshold_percent: float = Query(15, ge=5, le=50),
    min_days: int = Query(7, ge=3, le=30),
    db: AsyncSession = Depends(get_db),
):
    """
    Check doorways for CR drop and rollback. Call daily via cron.
    Respects campaign.affiliate_rules.ai.auto_rollback_on_cr_drop and rollback_threshold_percent.
    """
    since = datetime.utcnow() - timedelta(days=min_days)
    r = await db.execute(
        select(Doorway, Campaign.user_id, Campaign.affiliate_rules)
        .join(Campaign)
        .where(Doorway.status.in_(["deployed", "indexed"]))
    )
    rolled = 0
    for dw, user_id, aff_rules in r.all():
        rules = aff_rules or {}
        ai_conf = rules.get("ai") or {}
        if ai_conf.get("auto_rollback_on_cr_drop") is False:
            continue
        thresh = ai_conf.get("rollback_threshold_percent")
        if thresh is not None:
            threshold = float(thresh)
        else:
            threshold = threshold_percent
        r2 = await db.execute(
            select(
                func.sum(DoorwayMetrics.clicks).label("clicks"),
                func.sum(DoorwayMetrics.conversions).label("conv"),
            )
            .where(
                DoorwayMetrics.doorway_id == dw.id,
                DoorwayMetrics.date >= since,
            )
        )
        row = r2.first()
        if not row or not row.clicks or row.clicks < 30:
            continue
        half = min_days // 2
        mid = datetime.utcnow() - timedelta(days=half)
        r3 = await db.execute(
            select(
                func.sum(DoorwayMetrics.clicks).label("c1"),
                func.sum(DoorwayMetrics.conversions).label("c2"),
            )
            .where(
                DoorwayMetrics.doorway_id == dw.id,
                DoorwayMetrics.date >= since,
                DoorwayMetrics.date < mid,
            )
        )
        prev = r3.first()
        r4 = await db.execute(
            select(
                func.sum(DoorwayMetrics.clicks).label("c1"),
                func.sum(DoorwayMetrics.conversions).label("c2"),
            )
            .where(
                DoorwayMetrics.doorway_id == dw.id,
                DoorwayMetrics.date >= mid,
            )
        )
        recent = r4.first()
        if not prev or not prev.c1 or prev.c1 < 10 or not recent or not recent.c1 or recent.c1 < 10:
            continue
        cr_prev = prev.c2 / prev.c1 * 100 if prev.c1 else 0
        cr_recent = recent.c2 / recent.c1 * 100 if recent.c1 else 0
        if cr_prev > 0 and cr_recent < cr_prev * (1 - threshold / 100):
            ver_r = await db.execute(
                select(DoorwayVersion)
                .where(DoorwayVersion.doorway_id == dw.id)
                .order_by(DoorwayVersion.created_at.desc())
                .limit(2)
            )
            vers = list(ver_r.scalars().all())
            if len(vers) >= 2:
                snap = vers[1].content_snapshot
                if isinstance(snap, dict):
                    dw.title = snap.get("title", dw.title)
                    dw.content = snap.get("content", dw.content)
                    dw.meta_description = snap.get("meta_description", dw.meta_description)
                    rolled += 1
    await db.commit()
    return {"status": "ok", "rolled_back": rolled}


@router.post("/auto-pause-unprofitable")
async def auto_pause_unprofitable(
    min_revenue: float = Query(0),
    min_days: int = Query(14, ge=7),
    db: AsyncSession = Depends(get_db),
):
    """Pause doorways with negative ROI."""
    from sqlalchemy import func
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(days=min_days)
    r = await db.execute(
        select(Doorway, Campaign.user_id)
        .join(Campaign)
        .where(Doorway.status.in_(["deployed", "indexed"]))
    )
    paused = 0
    for dw, user_id in r.all():
        r2 = await db.execute(
            select(
                func.sum(DoorwayMetrics.revenue).label("rev"),
                func.sum(DoorwayMetrics.clicks).label("clk"),
            )
            .where(DoorwayMetrics.doorway_id == dw.id, DoorwayMetrics.date >= since)
        )
        row = r2.first()
        if row and row.rev is not None and row.rev < min_revenue and (row.clk or 0) >= 20:
            dw.status = "paused"
            paused += 1
            try:
                from app.services.webhook_service import notify_webhooks
                await notify_webhooks(db, user_id, "doorway.auto_paused", {
                    "doorway_id": dw.id, "revenue": float(row.rev or 0), "clicks": int(row.clk or 0),
                })
            except Exception:
                pass
    await db.commit()
    return {"status": "ok", "paused": paused}


@router.post("/auto-switch-offers")
async def auto_switch_offers_on_cr_drop(
    threshold_percent: float = Query(15, ge=5, le=50),
    min_days: int = Query(7, ge=3, le=30),
    db: AsyncSession = Depends(get_db),
):
    """
    When campaign CR drops and has 2+ offers, rotate priorities: demote top offer.
    Call daily via cron. Requires campaign.affiliate_rules.auto_switch_on_cr_drop = true
    (or enable for all campaigns with 2+ offers if not set).
    """
    since = datetime.utcnow() - timedelta(days=min_days)
    half = min_days // 2
    mid = datetime.utcnow() - timedelta(days=half)

    # Campaigns with 2+ active offers
    camp_r = await db.execute(
        select(Campaign.id, Campaign.affiliate_rules)
        .join(Offer, Offer.campaign_id == Campaign.id)
        .where(Offer.is_active == True)
        .group_by(Campaign.id)
        .having(func.count(Offer.id) >= 2)
    )
    campaigns = list(camp_r.all())
    switched = 0

    for camp_id, aff_rules in campaigns:
        rules = aff_rules or {}
        off_conf = rules.get("offers") or {}
        if off_conf.get("auto_switch_on_cr_drop") is False:
            continue

        # Aggregate CR for this campaign's doorways
        dw_subq = select(Doorway.id).where(Doorway.campaign_id == camp_id)
        prev_r = await db.execute(
            select(
                func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("c1"),
                func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("c2"),
            ).select_from(DoorwayMetrics).where(
                DoorwayMetrics.doorway_id.in_(dw_subq),
                DoorwayMetrics.date >= since,
                DoorwayMetrics.date < mid,
            )
        )
        prev_row = prev_r.first()
        recent_r = await db.execute(
            select(
                func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("c1"),
                func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("c2"),
            ).select_from(DoorwayMetrics).where(
                DoorwayMetrics.doorway_id.in_(dw_subq),
                DoorwayMetrics.date >= mid,
            )
        )
        recent_row = recent_r.first()
        if not prev_row or not recent_row or prev_row.c1 < 20 or recent_row.c1 < 20:
            continue
        cr_prev = prev_row.c2 / prev_row.c1 * 100 if prev_row.c1 else 0
        cr_recent = recent_row.c2 / recent_row.c1 * 100 if recent_row.c1 else 0
        if cr_prev <= 0 or cr_recent >= cr_prev * (1 - threshold_percent / 100):
            continue

        # CR dropped: swap priorities of top 2 offers
        off_r = await db.execute(
            select(Offer)
            .where(Offer.campaign_id == camp_id, Offer.is_active == True)
            .order_by(Offer.priority.desc())
            .limit(2)
        )
        offers = list(off_r.scalars().all())
        if len(offers) < 2:
            continue
        o1, o2 = offers[0], offers[1]
        p1, p2 = o1.priority or 0, o2.priority or 0
        o1.priority = min(p1, p2) - 1
        o2.priority = max(p1, p2) + 1
        switched += 1

    await db.commit()
    return {"status": "ok", "switched": switched}


@router.post("/pause-on-affiliate-issues")
async def pause_on_affiliate_issues(
    min_conversions_drop_percent: float = Query(50, ge=20, le=90),
    min_days: int = Query(7, ge=3),
    db: AsyncSession = Depends(get_db),
):
    """
    Pause doorways when campaign's affiliate shows issues (conversions drop).
    Compare last half-period vs previous half.
    """
    since = datetime.utcnow() - timedelta(days=min_days)
    half = min_days // 2
    mid = datetime.utcnow() - timedelta(days=half)

    r = await db.execute(
        select(Campaign.id).join(Doorway, Doorway.campaign_id == Campaign.id).where(Doorway.status.in_(["deployed", "indexed"]))
    )
    camp_ids = list({row[0] for row in r.all()})
    paused = 0

    for camp_id in camp_ids:
        dw_subq = select(Doorway.id).where(Doorway.campaign_id == camp_id)
        prev_r = await db.execute(
            select(func.sum(DoorwayMetrics.conversions).label("c"))
            .select_from(DoorwayMetrics)
            .where(DoorwayMetrics.doorway_id.in_(dw_subq), DoorwayMetrics.date >= since, DoorwayMetrics.date < mid)
        )
        recent_r = await db.execute(
            select(func.sum(DoorwayMetrics.conversions).label("c"))
            .select_from(DoorwayMetrics)
            .where(DoorwayMetrics.doorway_id.in_(dw_subq), DoorwayMetrics.date >= mid)
        )
        prev_c = (prev_r.scalar() or 0) or 0
        recent_c = (recent_r.scalar() or 0) or 0
        if prev_c < 10:
            continue
        drop = (prev_c - recent_c) / prev_c * 100 if prev_c else 0
        if drop < min_conversions_drop_percent:
            continue
        r2 = await db.execute(select(Doorway).where(Doorway.campaign_id == camp_id, Doorway.status.in_(["deployed", "indexed"])))
        for dw in r2.scalars().all():
            dw.status = "paused"
            paused += 1

    await db.commit()
    return {"status": "ok", "paused": paused}
