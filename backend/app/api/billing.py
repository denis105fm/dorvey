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


@router.get("/usage")
async def get_usage(current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    """Current user usage vs limits."""
    plan = await _get_plan(db, current_user.id)
    limits = PLANS.get(plan, PLANS["free"])

    dw_r = await db.execute(select(func.count(Doorway.id)).select_from(Doorway).join(Campaign).where(Campaign.user_id == current_user.id))
    camp_r = await db.execute(select(func.count(Campaign.id)).where(Campaign.user_id == current_user.id))
    dom_r = await db.execute(select(func.count(Domain.id)).join(Campaign, Domain.campaign_id == Campaign.id).where(Campaign.user_id == current_user.id))

    usage = {
        "doorways": dw_r.scalar() or 0,
        "campaigns": camp_r.scalar() or 0,
        "domains": dom_r.scalar() or 0,
    }
    return {
        "plan": plan,
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
