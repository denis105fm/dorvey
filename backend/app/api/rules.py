"""Rules builder API - structured affiliate_rules for campaigns."""
import copy
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, Any

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.campaign import Campaign

router = APIRouter()


class ConversionSettings(BaseModel):
    """Conversion UI: urgency, social_proof, exit_intent, cta_by_device (stored in affiliate_rules.settings)."""
    urgency_block: Optional[dict[str, Any] | str] = None
    social_proof: Optional[dict[str, Any] | str] = None
    exit_intent: Optional[dict[str, Any]] = None
    cta_by_device: Optional[dict[str, str]] = None
    show_offers_table: Optional[bool] = None  # If False, doorway shows content + single CTA only (no comparison table)


class RulesBuilder(BaseModel):
    forbidden_words: Optional[list[str]] = None
    allowed_geo: Optional[list[str]] = None
    require_disclaimer: Optional[bool] = None
    auto_switch_on_cr_drop: Optional[bool] = None
    auto_rollback_on_cr_drop: Optional[bool] = None
    rollback_threshold_percent: Optional[float] = None
    auto_generate_enabled: Optional[bool] = None
    cloaking_enabled: Optional[bool] = None
    cloaking_bot_patterns: Optional[list[str]] = None
    # Auto-apply AI recommendations when CR/CTR below threshold
    auto_apply_recommendations: Optional[bool] = None
    auto_apply_cr_threshold_percent: Optional[float] = None
    auto_apply_ctr_threshold_percent: Optional[float] = None
    auto_apply_min_clicks: Optional[int] = None
    auto_apply_min_impressions: Optional[int] = None
    preferred_layout_index: Optional[int] = None  # A/B winner layout for new doorways
    # Early pause: stop new doorways with traffic but 0 conversions in N days
    early_pause_enabled: Optional[bool] = None
    early_pause_min_days: Optional[int] = None
    early_pause_min_clicks: Optional[int] = None


async def _check(db, campaign_id: int, user_id: int):
    r = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id))
    return r.scalar_one_or_none()


@router.get("/presets")
async def get_conversion_presets(
    current_user: CurrentUser,
    lang: str = "ru",
    index: int = 0,
):
    """Return psychological conversion presets (urgency, social_proof, exit_intent, cta) for given lang. Index cycles presets."""
    from app.services.schema_helper import (
        get_urgency_preset,
        get_social_proof_preset,
        get_exit_intent_preset,
        get_cta_preset,
    )
    lang = (lang or "ru").lower()[:2]
    return {
        "urgency_block": {"text": get_urgency_preset(lang, index)},
        "social_proof": get_social_proof_preset(lang, index),
        "exit_intent": get_exit_intent_preset(lang, index),
        "cta_by_device": get_cta_preset(lang, index),
    }


@router.get("/campaign/{campaign_id}")
async def get_rules(campaign_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    c = await _check(db, campaign_id, current_user.id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    rules = c.affiliate_rules or {}
    rr = rules.get("rules") or {}
    offers_conf = rules.get("offers") or {}
    ai_conf = rules.get("ai") or {}
    cloaking = rules.get("cloaking") or {}
    default_bots = ["Googlebot", "YandexBot", "bingbot", "Slurp", "DuckDuckBot"]
    return {
        "forbidden_words": rr.get("forbidden_words", []),
        "allowed_geo": rr.get("allowed_geo", []),
        "require_disclaimer": rr.get("require_disclaimer", False),
        "auto_switch_on_cr_drop": offers_conf.get("auto_switch_on_cr_drop"),
        "auto_rollback_on_cr_drop": ai_conf.get("auto_rollback_on_cr_drop"),
        "rollback_threshold_percent": ai_conf.get("rollback_threshold_percent"),
        "auto_generate_enabled": rules.get("auto_generate_enabled", False),
        "cloaking_enabled": isinstance(cloaking, dict) and bool(cloaking.get("enabled")),
        "cloaking_bot_patterns": (isinstance(cloaking, dict) and cloaking.get("bot_patterns")) or default_bots,
        "auto_apply_recommendations": ai_conf.get("auto_apply_recommendations", False),
        "auto_apply_cr_threshold_percent": ai_conf.get("auto_apply_cr_threshold_percent"),
        "auto_apply_ctr_threshold_percent": ai_conf.get("auto_apply_ctr_threshold_percent"),
        "auto_apply_min_clicks": ai_conf.get("auto_apply_min_clicks"),
        "auto_apply_min_impressions": ai_conf.get("auto_apply_min_impressions"),
        "preferred_layout_index": ai_conf.get("preferred_layout_index"),
        "early_pause_enabled": (rules.get("early_pause") or {}).get("enabled", True),
        "early_pause_min_days": (rules.get("early_pause") or {}).get("min_days", 2),
        "early_pause_min_clicks": (rules.get("early_pause") or {}).get("min_clicks", 30),
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
    if data.cloaking_enabled is not None:
        if "cloaking" not in rules:
            rules["cloaking"] = {}
        rules["cloaking"] = {**(rules.get("cloaking") or {}), "enabled": data.cloaking_enabled}
    if data.cloaking_bot_patterns is not None:
        if "cloaking" not in rules:
            rules["cloaking"] = {}
        rules["cloaking"] = {**(rules.get("cloaking") or {}), "bot_patterns": data.cloaking_bot_patterns}
    if data.auto_apply_recommendations is not None:
        rules["ai"]["auto_apply_recommendations"] = data.auto_apply_recommendations
    if data.auto_apply_cr_threshold_percent is not None:
        rules["ai"]["auto_apply_cr_threshold_percent"] = data.auto_apply_cr_threshold_percent
    if data.auto_apply_ctr_threshold_percent is not None:
        rules["ai"]["auto_apply_ctr_threshold_percent"] = data.auto_apply_ctr_threshold_percent
    if data.auto_apply_min_clicks is not None:
        rules["ai"]["auto_apply_min_clicks"] = data.auto_apply_min_clicks
    if data.auto_apply_min_impressions is not None:
        rules["ai"]["auto_apply_min_impressions"] = data.auto_apply_min_impressions
    if "preferred_layout_index" in data.model_dump(exclude_unset=True):
        rules["ai"]["preferred_layout_index"] = data.preferred_layout_index
    if data.early_pause_enabled is not None or data.early_pause_min_days is not None or data.early_pause_min_clicks is not None:
        rules["early_pause"] = {**(rules.get("early_pause") or {})}
        if data.early_pause_enabled is not None:
            rules["early_pause"]["enabled"] = data.early_pause_enabled
        if data.early_pause_min_days is not None:
            rules["early_pause"]["min_days"] = data.early_pause_min_days
    if data.early_pause_min_clicks is not None:
        rules["early_pause"]["min_clicks"] = data.early_pause_min_clicks
    # Глубокое копирование, чтобы ORM зафиксировал изменение JSON-поля (при мутации вложенных dict объект мог не помечаться как изменённый)
    c.affiliate_rules = copy.deepcopy(rules)
    await db.commit()
    return {"status": "ok"}


@router.get("/campaign/{campaign_id}/conversion")
async def get_conversion(campaign_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    c = await _check(db, campaign_id, current_user.id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    settings = (c.affiliate_rules or {}).get("settings") or {}
    return {
        "urgency_block": settings.get("urgency_block"),
        "social_proof": settings.get("social_proof"),
        "exit_intent": settings.get("exit_intent"),
        "cta_by_device": settings.get("cta_by_device"),
        "show_offers_table": settings.get("show_offers_table", False),
    }


@router.put("/campaign/{campaign_id}/conversion")
async def update_conversion(campaign_id: int, data: ConversionSettings, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    c = await _check(db, campaign_id, current_user.id)
    if not c:
        raise HTTPException(404, "Campaign not found")
    rules = dict(c.affiliate_rules or {})
    if "settings" not in rules:
        rules["settings"] = {}
    settings = dict(rules["settings"])
    if data.urgency_block is not None:
        settings["urgency_block"] = data.urgency_block
    if data.social_proof is not None:
        settings["social_proof"] = data.social_proof
    if data.exit_intent is not None:
        settings["exit_intent"] = data.exit_intent
    if data.cta_by_device is not None:
        settings["cta_by_device"] = data.cta_by_device
    if data.show_offers_table is not None:
        settings["show_offers_table"] = data.show_offers_table
    rules["settings"] = settings
    c.affiliate_rules = rules
    await db.commit()
    return {"status": "ok"}
