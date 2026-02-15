"""Rules builder API - structured affiliate_rules for campaigns."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.campaign import Campaign

router = APIRouter()


class RulesBuilder(BaseModel):
    forbidden_words: Optional[list[str]] = None
    allowed_geo: Optional[list[str]] = None
    require_disclaimer: Optional[bool] = None
    auto_switch_on_cr_drop: Optional[bool] = None
    auto_rollback_on_cr_drop: Optional[bool] = None
    rollback_threshold_percent: Optional[float] = None
    auto_generate_enabled: Optional[bool] = None


async def _check(db, campaign_id: int, user_id: int):
    r = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id))
    return r.scalar_one_or_none()


@router.get("/campaign/{campaign_id}")
async def get_rules(campaign_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    c = await _check(db, campaign_id, current_user.id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    rules = c.affiliate_rules or {}
    rr = rules.get("rules") or {}
    offers_conf = rules.get("offers") or {}
    ai_conf = rules.get("ai") or {}
    return {
        "forbidden_words": rr.get("forbidden_words", []),
        "allowed_geo": rr.get("allowed_geo", []),
        "require_disclaimer": rr.get("require_disclaimer", False),
        "auto_switch_on_cr_drop": offers_conf.get("auto_switch_on_cr_drop"),
        "auto_rollback_on_cr_drop": ai_conf.get("auto_rollback_on_cr_drop"),
        "rollback_threshold_percent": ai_conf.get("rollback_threshold_percent"),
        "auto_generate_enabled": rules.get("auto_generate_enabled", False),
    }


@router.put("/campaign/{campaign_id}")
async def update_rules(campaign_id: int, data: RulesBuilder, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    c = await _check(db, campaign_id, current_user.id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    rules = dict(c.affiliate_rules or {})
    if "rules" not in rules:
        rules["rules"] = {}
    if "offers" not in rules:
        rules["offers"] = {}
    if "ai" not in rules:
        rules["ai"] = {}
    if data.forbidden_words is not None:
        rules["rules"]["forbidden_words"] = data.forbidden_words
    if data.allowed_geo is not None:
        rules["rules"]["allowed_geo"] = data.allowed_geo
    if data.require_disclaimer is not None:
        rules["rules"]["require_disclaimer"] = data.require_disclaimer
    if data.auto_switch_on_cr_drop is not None:
        rules["offers"]["auto_switch_on_cr_drop"] = data.auto_switch_on_cr_drop
    if data.auto_rollback_on_cr_drop is not None:
        rules["ai"]["auto_rollback_on_cr_drop"] = data.auto_rollback_on_cr_drop
    if data.rollback_threshold_percent is not None:
        rules["ai"]["rollback_threshold_percent"] = data.rollback_threshold_percent
    if data.auto_generate_enabled is not None:
        rules["auto_generate_enabled"] = data.auto_generate_enabled
    c.affiliate_rules = rules
    await db.commit()
    return {"status": "ok"}
