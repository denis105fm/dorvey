"""Traffic mix: распределение трафика между дорвеями/офферами по ROI."""
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doorway import Doorway, DoorwayMetrics
from app.models.campaign import Campaign


async def get_traffic_mix_recommendations(
    db: AsyncSession,
    campaign_id: int,
    user_id: int,
    days: int = 14,
) -> List[dict]:
    """
    Рекомендации по трафик-миксу: какие дорвеи усиливать, какие снижать
    на основе ROI (revenue/clicks), CR, позиций.
    """
    since = datetime.utcnow() - timedelta(days=days)
    r = await db.execute(
        select(Doorway)
        .join(Campaign)
        .where(Doorway.campaign_id == campaign_id, Campaign.user_id == user_id)
    )
    doorways = r.scalars().all()
    if not doorways:
        return []

    results = []
    for dw in doorways:
        m_r = await db.execute(
            select(
                func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clk"),
                func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conv"),
                func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("rev"),
            ).where(DoorwayMetrics.doorway_id == dw.id, DoorwayMetrics.date >= since)
        )
        row = m_r.first()
        clk = int(row.clk or 0)
        conv = int(row.conv or 0)
        rev = float(row.rev or 0)
        cr = (conv / clk * 100) if clk else 0
        roi = (rev / clk) if clk else 0

        action = "hold"
        if clk >= 20:
            if roi > 0 and cr >= 2:
                action = "boost"
            elif roi < 0 or (clk >= 50 and conv == 0):
                action = "reduce"

        results.append({
            "doorway_id": dw.id,
            "title": dw.title or "",
            "clicks": clk,
            "conversions": conv,
            "revenue": rev,
            "cr_percent": round(cr, 2),
            "roi_per_click": round(roi, 4),
            "action": action,
        })

    return sorted(results, key=lambda x: -x["roi_per_click"])
