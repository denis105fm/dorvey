"""Billing API: limits, usage, plans."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.doorway import Doorway
from app.models.campaign import Campaign
from app.models.domain import Domain
from app.models.setting import Setting

router = APIRouter()

PLANS = {
    "free": {"doorways": 50, "campaigns": 5, "domains": 3, "price": 0},
    "pro": {"doorways": 500, "campaigns": 50, "domains": 20, "price": 29},
    "enterprise": {"doorways": 5000, "campaigns": 500, "domains": 100, "price": 99},
}


async def _get_plan(db: AsyncSession, user_id: int) -> str:
    r = await db.execute(select(Setting).where(Setting.user_id == user_id, Setting.key == "billing_plan"))
    s = r.scalar_one_or_none()
    return (s.value or "free").strip().lower() if s and s.value else "free"


async def _get_usage_and_limits(db: AsyncSession, user_id: int) -> dict:
    plan = await _get_plan(db, user_id)
    limits = PLANS.get(plan, PLANS["free"])
    dw_r = await db.execute(select(func.count(Doorway.id)).select_from(Doorway).join(Campaign).where(Campaign.user_id == user_id))
    camp_r = await db.execute(select(func.count(Campaign.id)).where(Campaign.user_id == user_id))
    dom_r = await db.execute(select(func.count(Domain.id)).join(Campaign, Domain.campaign_id == Campaign.id).where(Campaign.user_id == user_id))
    usage = {
        "doorways": dw_r.scalar() or 0,
        "campaigns": camp_r.scalar() or 0,
        "domains": dom_r.scalar() or 0,
    }
    return {"plan": plan, "limits": limits, "usage": usage}


async def notify_billing_limits_if_needed(db: AsyncSession, user_id: int) -> None:
    """If usage >= 80% or >= 100% of any limit, send webhook events (billing.near_limit / billing.over_limit)."""
    data = await _get_usage_and_limits(db, user_id)
    usage = data["usage"]
    limits = data["limits"]
    try:
        from app.services.webhook_service import notify_webhooks
        for resource in ["doorways", "campaigns", "domains"]:
            u = usage[resource]
            lim = limits.get(resource, 0)
            if lim <= 0:
                continue
            pct = (u / lim * 100) if lim else 0
            if u >= lim:
                await notify_webhooks(db, user_id, "billing.over_limit", {
                    "resource": resource,
                    "usage": u,
                    "limit": lim,
                    "percent": round(pct, 1),
                    "plan": data["plan"],
                })
            elif pct >= 80:
                await notify_webhooks(db, user_id, "billing.near_limit", {
                    "resource": resource,
                    "usage": u,
                    "limit": lim,
                    "percent": round(pct, 1),
                    "plan": data["plan"],
                })
    except Exception:
        pass


@router.get("/usage")
async def get_usage(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Current user usage vs limits."""
    data = await _get_usage_and_limits(db, current_user.id)
    usage = data["usage"]
    limits = data["limits"]
    return {
        "plan": data["plan"],
        "limits": limits,
        "usage": usage,
        "over_limit": {
            k: usage[k] >= limits.get(k, 0) for k in ["doorways", "campaigns", "domains"]
        },
    }


@router.get("/plans")
async def list_plans():
    """Available plans."""
    return list(PLANS.items())
