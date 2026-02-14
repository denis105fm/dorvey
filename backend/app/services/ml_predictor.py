"""ML: CR/position prediction, anomaly detection."""

from datetime import datetime, timedelta
from typing import List, Optional
import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doorway import Doorway, DoorwayMetrics
from app.models.campaign import Campaign


async def predict_cr(
    db: AsyncSession,
    doorway_id: int,
    days_history: int = 30,
) -> Optional[dict]:
    """
    Simple CR prediction from recent trend (linear regression).
    Returns {predicted_cr, trend, confidence}.
    """
    since = datetime.utcnow() - timedelta(days=days_history)
    day_col = func.date_trunc("day", DoorwayMetrics.date)
    r = await db.execute(
        select(
            day_col.label("day"),
            func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clicks"),
            func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conv"),
        )
        .where(DoorwayMetrics.doorway_id == doorway_id, DoorwayMetrics.date >= since)
        .group_by(day_col)
        .order_by(day_col)
    )
    rows = r.all()
    if len(rows) < 5:
        return None
    cr_values = []
    for row in rows:
        clk = row.clicks or 0
        if clk > 0:
            cr_values.append((row.conv or 0) / clk * 100)
    if len(cr_values) < 3:
        return None
    x = np.arange(len(cr_values))
    y = np.array(cr_values)
    coeffs = np.polyfit(x, y, 1)
    trend = float(coeffs[0])
    pred = float(np.polyval(coeffs, len(cr_values) + 7))
    coeffs = np.polyfit(x, y, 1)
    trend = float(coeffs[0])
    pred = float(np.polyval(coeffs, len(cr_values) + 7))
    model_used = "linear"
    try:
        import xgboost as xgb
        if len(cr_values) >= 10:
            dtrain = xgb.DMatrix(x.reshape(-1, 1), label=y)
            bst = xgb.train({"objective": "reg:squarederror", "max_depth": 3}, dtrain, num_boost_round=30)
            pred = float(bst.predict(xgb.DMatrix(np.array([[len(cr_values) + 7]]))))
            model_used = "xgboost"
    except ImportError:
        pass

    return {
        "predicted_cr_7d": round(max(0, pred), 2),
        "trend_per_day": round(trend, 4),
        "current_cr": round(cr_values[-1], 2),
        "data_points": len(cr_values),
        "model": model_used,
    }


async def detect_anomalies(
    db: AsyncSession,
    user_id: int,
    days: int = 14,
) -> List[dict]:
    """
    Detect anomalies: unusual CR drop, position drop, zero conversions.
    Returns list of {doorway_id, type, severity, message}.
    """
    since = datetime.utcnow() - timedelta(days=days)
    half = days // 2
    mid = datetime.utcnow() - timedelta(days=half)

    r = await db.execute(
        select(Doorway, Campaign.user_id)
        .join(Campaign)
        .where(Campaign.user_id == user_id, Doorway.status.in_(["deployed", "indexed"]))
    )
    anomalies = []
    for dw, uid in r.all():
        # CR drop
        prev_r = await db.execute(
            select(
                func.sum(DoorwayMetrics.clicks).label("c1"),
                func.sum(DoorwayMetrics.conversions).label("c2"),
            ).where(
                DoorwayMetrics.doorway_id == dw.id,
                DoorwayMetrics.date >= since,
                DoorwayMetrics.date < mid,
            )
        )
        prev = prev_r.first()
        recent_r = await db.execute(
            select(
                func.sum(DoorwayMetrics.clicks).label("c1"),
                func.sum(DoorwayMetrics.conversions).label("c2"),
            ).where(
                DoorwayMetrics.doorway_id == dw.id,
                DoorwayMetrics.date >= mid,
            )
        )
        recent = recent_r.first()
        if prev and recent and prev.c1 and prev.c1 >= 20 and recent.c1 and recent.c1 >= 10:
            cr_prev = prev.c2 / prev.c1 * 100
            cr_recent = recent.c2 / recent.c1 * 100
            if cr_prev > 0 and cr_recent < cr_prev * 0.5:
                anomalies.append({
                    "doorway_id": dw.id,
                    "type": "cr_drop",
                    "severity": "high",
                    "message": f"CR упал с {cr_prev:.1f}% до {cr_recent:.1f}%",
                })
        # Zero conversions but many clicks
        total_r = await db.execute(
            select(
                func.sum(DoorwayMetrics.clicks).label("clk"),
                func.sum(DoorwayMetrics.conversions).label("conv"),
            ).where(DoorwayMetrics.doorway_id == dw.id, DoorwayMetrics.date >= since)
        )
        tot = total_r.first()
        if tot and tot.clk and tot.clk >= 50 and (tot.conv or 0) == 0:
            anomalies.append({
                "doorway_id": dw.id,
                "type": "zero_conversions",
                "severity": "medium",
                "message": f"{tot.clk} кликов, 0 конверсий",
            })
    return anomalies
