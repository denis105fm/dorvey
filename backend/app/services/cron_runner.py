"""Cron logic — shared by API and Celery."""

from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doorway import Doorway, DoorwayMetrics, DoorwayVersion
from app.models.campaign import Campaign
from app.models.offer import Offer


async def run_auto_rollback(
    db: AsyncSession,
    threshold_percent: float = 15,
    min_days: int = 7,
) -> dict:
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
        threshold = float(thresh) if thresh is not None else threshold_percent
        r2 = await db.execute(
            select(
                func.sum(DoorwayMetrics.clicks).label("clicks"),
                func.sum(DoorwayMetrics.conversions).label("conv"),
            )
            .where(DoorwayMetrics.doorway_id == dw.id, DoorwayMetrics.date >= since)
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
    return {"rolled_back": rolled}


async def run_early_pause_no_conversions(
    db: AsyncSession,
    min_days: int = 2,
    min_clicks: int = 30,
) -> dict:
    """
    Пауза новых дорвеев (deployed за последние min_days дней): 0 конверсий при достаточном трафике.
    Даёт прибыль уже на 2–3 день: не жжём бюджет на мёртвых дорвеях.
    Опция в кампании: affiliate_rules.early_pause { enabled, min_days, min_clicks }. По умолчанию включено.
    """
    since = datetime.utcnow() - timedelta(days=min_days)
    r = await db.execute(
        select(Doorway, Campaign.user_id, Campaign.affiliate_rules)
        .join(Campaign)
        .where(
            Doorway.status.in_(["deployed", "indexed"]),
            Doorway.deployed_at.isnot(None),
            Doorway.deployed_at >= since,
        )
    )
    paused = 0
    for dw, user_id, aff_rules in r.all():
        rules = aff_rules or {}
        ep = rules.get("early_pause") or {}
        if ep.get("enabled") is False:
            continue
        md = int(ep.get("min_days") or min_days)
        mc = int(ep.get("min_clicks") or min_clicks)
        since_d = datetime.utcnow() - timedelta(days=md)
        r2 = await db.execute(
            select(
                func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clk"),
                func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conv"),
                func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("rev"),
            )
            .where(
                DoorwayMetrics.doorway_id == dw.id,
                DoorwayMetrics.date >= since_d,
            )
        )
        row = r2.first()
        if not row or (row.conv or 0) > 0 or (row.rev or 0) > 0:
            continue
        if (row.clk or 0) < mc:
            continue
        dw.status = "paused"
        dw.pause_reason = (
            f"Ранний стоп: за последние {md} дн. {int(row.clk or 0)} кликов, 0 конверсий. "
            "Смените оффер или проверьте постбек."
        )
        paused += 1
        try:
            from app.services.webhook_service import notify_webhooks
            await notify_webhooks(db, user_id, "doorway.auto_paused", {
                "doorway_id": dw.id, "clicks": int(row.clk or 0), "reason": "early_no_conversions",
            })
        except Exception:
            pass
    await db.commit()
    return {"paused": paused}


async def run_early_pause_24h(
    db: AsyncSession,
    min_clicks: int = 50,
) -> dict:
    """
    Жёсткий ранний стоп за 24 ч: 0 конверсий и >= min_clicks за последние сутки → пауза.
    Опция в кампании: affiliate_rules.early_pause_24h { enabled, min_clicks }. По умолчанию включено.
    """
    since = datetime.utcnow() - timedelta(hours=24)
    r = await db.execute(
        select(Doorway, Campaign.user_id, Campaign.affiliate_rules)
        .join(Campaign)
        .where(Doorway.status.in_(["deployed", "indexed"]))
    )
    paused = 0
    for dw, user_id, aff_rules in r.all():
        rules = aff_rules or {}
        ep = rules.get("early_pause_24h") or {}
        if ep.get("enabled") is False:
            continue
        mc = int(ep.get("min_clicks") or min_clicks)
        r2 = await db.execute(
            select(
                func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clk"),
                func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conv"),
                func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("rev"),
            )
            .where(
                DoorwayMetrics.doorway_id == dw.id,
                DoorwayMetrics.date >= since,
            )
        )
        row = r2.first()
        if not row or (row.conv or 0) > 0 or (row.rev or 0) > 0:
            continue
        if (row.clk or 0) < mc:
            continue
        dw.status = "paused"
        dw.pause_reason = (
            f"Ранний стоп 24ч: за сутки {int(row.clk or 0)} кликов, 0 конверсий. "
            "Смените оффер или проверьте постбек."
        )
        paused += 1
        try:
            from app.services.webhook_service import notify_webhooks
            await notify_webhooks(db, user_id, "doorway.auto_paused", {
                "doorway_id": dw.id, "clicks": int(row.clk or 0), "reason": "early_pause_24h",
            })
        except Exception:
            pass
    await db.commit()
    return {"paused": paused}


async def run_auto_pause_unprofitable(
    db: AsyncSession,
    min_revenue: float = 0,
    min_days: int = 14,
) -> dict:
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
            dw.pause_reason = (
                "Мало выручки за период при достаточном трафике (≥20 кликов). "
                "Включите постбек или проверьте оффер."
            )
            paused += 1
            try:
                from app.services.webhook_service import notify_webhooks
                await notify_webhooks(db, user_id, "doorway.auto_paused", {
                    "doorway_id": dw.id, "revenue": float(row.rev or 0), "clicks": int(row.clk or 0),
                })
            except Exception:
                pass
    await db.commit()
    return {"paused": paused}


async def run_auto_switch_offers(
    db: AsyncSession,
    threshold_percent: float = 15,
    min_days: int = 7,
) -> dict:
    since = datetime.utcnow() - timedelta(days=min_days)
    half = min_days // 2
    mid = datetime.utcnow() - timedelta(days=half)
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
        dw_subq = select(Doorway.id).where(Doorway.campaign_id == camp_id)
        prev_r = await db.execute(
            select(
                func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("c1"),
                func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("c2"),
            )
            .select_from(DoorwayMetrics)
            .where(
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
            )
            .select_from(DoorwayMetrics)
            .where(
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
    return {"switched": switched}


async def run_pause_on_affiliate_issues(
    db: AsyncSession,
    min_conversions_drop_percent: float = 50,
    min_days: int = 7,
) -> dict:
    since = datetime.utcnow() - timedelta(days=min_days)
    half = min_days // 2
    mid = datetime.utcnow() - timedelta(days=half)
    r = await db.execute(
        select(Campaign.id)
        .join(Doorway, Doorway.campaign_id == Campaign.id)
        .where(Doorway.status.in_(["deployed", "indexed"]))
    )
    camp_ids = list({row[0] for row in r.all()})
    paused = 0
    for camp_id in camp_ids:
        dw_subq = select(Doorway.id).where(Doorway.campaign_id == camp_id)
        prev_r = await db.execute(
            select(func.sum(DoorwayMetrics.conversions).label("c"))
            .select_from(DoorwayMetrics)
            .where(
                DoorwayMetrics.doorway_id.in_(dw_subq),
                DoorwayMetrics.date >= since,
                DoorwayMetrics.date < mid,
            )
        )
        recent_r = await db.execute(
            select(func.sum(DoorwayMetrics.conversions).label("c"))
            .select_from(DoorwayMetrics)
            .where(
                DoorwayMetrics.doorway_id.in_(dw_subq),
                DoorwayMetrics.date >= mid,
            )
        )
        prev_c = (prev_r.scalar() or 0) or 0
        recent_c = (recent_r.scalar() or 0) or 0
        if prev_c < 10:
            continue
        drop = (prev_c - recent_c) / prev_c * 100 if prev_c else 0
        if drop < min_conversions_drop_percent:
            continue
        r2 = await db.execute(
            select(Doorway).where(
                Doorway.campaign_id == camp_id,
                Doorway.status.in_(["deployed", "indexed"]),
            )
        )
        for dw in r2.scalars().all():
            dw.status = "paused"
            paused += 1
    await db.commit()
    return {"paused": paused}


async def run_auto_apply_recommendations(
    db: AsyncSession,
    days: int = 14,
) -> dict:
    """
    For campaigns with auto_apply_recommendations=True: find doorways where CR or CTR
    is below threshold, get AI recommendations, apply first one. Max 1 apply per doorway
    per run (skip if last DoorwayVersion was created in last 24h).
    """
    from app.services.ai_optimizer import get_recommendations, apply_recommendation

    since = datetime.utcnow() - timedelta(days=days)
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)
    camp_r2 = await db.execute(select(Campaign.id, Campaign.user_id, Campaign.affiliate_rules))
    applied = 0
    for camp_id, user_id, aff_rules in camp_r2.all():
        rules = aff_rules or {}
        ai_conf = rules.get("ai") or {}
        if not ai_conf.get("auto_apply_recommendations"):
            continue
        cr_threshold = float(ai_conf.get("auto_apply_cr_threshold_percent") or 1.5)
        ctr_threshold = float(ai_conf.get("auto_apply_ctr_threshold_percent") or 2.0)
        min_clicks = int(ai_conf.get("auto_apply_min_clicks") or 30)
        min_impressions = int(ai_conf.get("auto_apply_min_impressions") or 100)

        dw_r = await db.execute(
            select(Doorway).where(
                Doorway.campaign_id == camp_id,
                Doorway.status.in_(["deployed", "indexed"]),
            )
        )
        for dw in dw_r.scalars().all():
            m_r = await db.execute(
                select(
                    func.coalesce(func.sum(DoorwayMetrics.impressions), 0).label("imp"),
                    func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clk"),
                    func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conv"),
                ).where(
                    DoorwayMetrics.doorway_id == dw.id,
                    DoorwayMetrics.date >= since,
                )
            )
            row = m_r.first()
            if not row or (row.clk or 0) < min_clicks:
                continue
            if (row.imp or 0) < min_impressions:
                continue
            imp, clk, conv = int(row.imp or 0), int(row.clk or 0), int(row.conv or 0)
            ctr = (clk / imp * 100) if imp else 0
            cr = (conv / clk * 100) if clk else 0
            if cr >= cr_threshold and ctr >= ctr_threshold:
                continue
            # Skip if we already applied in last 24h (last DoorwayVersion)
            ver_r = await db.execute(
                select(DoorwayVersion)
                .where(DoorwayVersion.doorway_id == dw.id)
                .order_by(DoorwayVersion.created_at.desc())
                .limit(1)
            )
            last_ver = ver_r.scalar_one_or_none()
            if last_ver and last_ver.created_at and last_ver.created_at >= cutoff_24h:
                continue
            recs = await get_recommendations(db, dw.id, days=days)
            if not recs or not isinstance(recs, list):
                continue
            rec = recs[0]
            rec_type = rec.get("type") or "content"
            rec_text = rec.get("text") or ""
            if not rec_text:
                continue
            ok, _, _ = await apply_recommendation(db, dw.id, rec_type, rec_text)
            if ok:
                applied += 1
                try:
                    from app.services.webhook_service import notify_webhooks
                    await notify_webhooks(db, user_id, "doorway.auto_fix", {
                        "doorway_id": dw.id, "rec_type": rec_type,
                    })
                except Exception:
                    pass
                break  # one per campaign per run to spread load
    return {"applied": applied}


async def run_anomaly_alerts(db: AsyncSession, days: int = 14) -> dict:
    """Detect anomalies and send notifications (Telegram/Slack/Email)."""
    from app.services.ml_predictor import detect_anomalies
    from app.services.webhook_service import notify_webhooks

    r = await db.execute(select(Campaign.user_id).distinct())
    user_ids = [row[0] for row in r.all()]
    total_notified = 0
    for uid in user_ids:
        anomalies = await detect_anomalies(db, uid, days=days)
        for a in anomalies:
            try:
                await notify_webhooks(db, uid, "doorway.anomaly", {
                    "doorway_id": a["doorway_id"],
                    "type": a["type"],
                    "severity": a.get("severity", "medium"),
                    "message": a.get("message", ""),
                })
                total_notified += 1
            except Exception:
                pass
    return {"anomalies_notified": total_notified}


async def run_all(db: AsyncSession) -> dict:
    """Run all daily cron tasks."""
    r0 = await run_anomaly_alerts(db, days=14)
    r_early = await run_early_pause_no_conversions(db, min_days=2, min_clicks=30)
    r_early24 = await run_early_pause_24h(db, min_clicks=50)
    r1 = await run_auto_rollback(db, threshold_percent=15, min_days=7)
    r2 = await run_auto_pause_unprofitable(db, min_revenue=0, min_days=14)
    r3 = await run_auto_switch_offers(db, threshold_percent=15, min_days=7)
    r4 = await run_pause_on_affiliate_issues(db, min_conversions_drop_percent=50, min_days=7)
    r5 = await run_auto_apply_recommendations(db, days=14)
    return {
        "status": "ok",
        "anomaly_alerts": r0,
        "early_pause_no_conversions": r_early,
        "early_pause_24h": r_early24,
        "auto_rollback": r1,
        "auto_pause_unprofitable": r2,
        "auto_switch_offers": r3,
        "pause_on_affiliate_issues": r4,
        "auto_apply_recommendations": r5,
    }
