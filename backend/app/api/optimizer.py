"""AI Optimizer API."""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.doorway import Doorway
from app.models.campaign import Campaign

from app.services.ai_optimizer import (
    get_recommendations,
    rollback_doorway,
    get_ab_winner,
    apply_recommendation,
    copy_winner_to_doorway,
    get_best_doorway_by_cr,
    get_pause_recommendations,
)
from app.services.ml_predictor import predict_cr, detect_anomalies
from app.services.traffic_mix import get_traffic_mix_recommendations

router = APIRouter()


class ApplyRecommendationRequest(BaseModel):
    rec_type: str  # ctr | cr | position | content
    rec_text: str


async def _check_campaign_access(db: AsyncSession, campaign_id: int, user_id: int) -> bool:
    r = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
    )
    return r.scalar_one_or_none() is not None


async def _check_access(db: AsyncSession, doorway_id: int, user_id: int) -> bool:
    r = await db.execute(
        select(Doorway).join(Campaign).where(
            Doorway.id == doorway_id, Campaign.user_id == user_id
        )
    )
    return r.scalar_one_or_none() is not None


@router.post("/doorway/{doorway_id}/apply-recommendation")
async def doorway_apply_recommendation(
    data: ApplyRecommendationRequest,
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Apply AI-generated fix for a recommendation (auto-fix)."""
    if not await _check_access(db, doorway_id, current_user.id):
        raise HTTPException(status_code=404, detail="Doorway not found")
    ok, msg, updated = await apply_recommendation(db, doorway_id, data.rec_type, data.rec_text)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    try:
        from app.services.webhook_service import notify_webhooks
        await notify_webhooks(db, current_user.id, "doorway.auto_fix", {"doorway_id": doorway_id, "rec_type": data.rec_type})
    except Exception:
        pass
    return {"status": "ok", "message": msg, "updated": updated}


@router.get("/doorway/{doorway_id}/recommendations")
async def doorway_recommendations(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(14, ge=7, le=90),
):
    if not await _check_access(db, doorway_id, current_user.id):
        raise HTTPException(status_code=404, detail="Doorway not found")
    return await get_recommendations(db, doorway_id, days=days)


@router.get("/doorway/{doorway_id}/pause-recommendations")
async def doorway_pause_recommendations(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(14, ge=7, le=90),
):
    """Рекомендации для дорвея на паузе: какой вариант A/B в кампании даёт лучший результат."""
    if not await _check_access(db, doorway_id, current_user.id):
        raise HTTPException(status_code=404, detail="Doorway not found")
    return await get_pause_recommendations(db, doorway_id, current_user.id, days=days)


@router.post("/doorway/{doorway_id}/rollback")
async def doorway_rollback(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if not await _check_access(db, doorway_id, current_user.id):
        raise HTTPException(status_code=404, detail="Doorway not found")
    ok, msg = await rollback_doorway(db, doorway_id)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    try:
        from app.services.webhook_service import notify_webhooks
        await notify_webhooks(db, current_user.id, "doorway.rollback", {"doorway_id": doorway_id})
    except Exception:
        pass
    return {"status": "ok", "message": msg}


@router.get("/campaign/{campaign_id}/ab-winner")
async def campaign_ab_winner(
    campaign_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(14, ge=7, le=90),
):
    """
    A/B winner: compare layout variants across campaign doorways.
    Returns best performing layout index and per-variant stats.
    """
    if not await _check_campaign_access(db, campaign_id, current_user.id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    return await get_ab_winner(db, campaign_id, days=days)


@router.get("/doorway/{doorway_id}/predict-cr")
async def doorway_predict_cr(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(30, ge=7, le=90),
):
    """Predict CR from recent trend (ML)."""
    if not await _check_access(db, doorway_id, current_user.id):
        raise HTTPException(404, "Doorway not found")
    r = await predict_cr(db, doorway_id, days_history=days)
    return r or {"message": "Insufficient data"}


@router.get("/campaign/{campaign_id}/traffic-mix")
async def campaign_traffic_mix(
    campaign_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(14, ge=7, le=90),
):
    """Traffic mix recommendations: boost/reduce/hold per doorway."""
    if not await _check_campaign_access(db, campaign_id, current_user.id):
        raise HTTPException(404, "Campaign not found")
    return await get_traffic_mix_recommendations(db, campaign_id, current_user.id, days=days)


class CopyWinnerRequest(BaseModel):
    source_doorway_id: int
    target_doorway_id: int


@router.post("/campaign/{campaign_id}/copy-winner")
async def campaign_copy_winner(
    campaign_id: int,
    data: CopyWinnerRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Copy content from best doorway to another doorway in the same campaign.
    Or auto-detect best: source_doorway_id=0 → use best by CR.
    """
    if not await _check_campaign_access(db, campaign_id, current_user.id):
        raise HTTPException(404, "Campaign not found")
    # Check target is in campaign
    r = await db.execute(
        select(Doorway).join(Campaign).where(
            Doorway.id == data.target_doorway_id,
            Doorway.campaign_id == campaign_id,
            Campaign.user_id == current_user.id,
        )
    )
    if not r.scalar_one_or_none():
        raise HTTPException(404, "Target doorway not found in campaign")
    source_id = data.source_doorway_id
    if source_id == 0:
        source_id = await get_best_doorway_by_cr(db, campaign_id, current_user.id)
        if not source_id:
            raise HTTPException(400, "Нет дорвеев с достаточными данными (min 20 кликов)")
    ok, msg = await copy_winner_to_doorway(
        db, source_id, data.target_doorway_id, current_user.id
    )
    if not ok:
        raise HTTPException(400, msg)
    try:
        from app.services.webhook_service import notify_webhooks
        await notify_webhooks(db, current_user.id, "doorway.copy_winner", {
            "source_doorway_id": source_id,
            "target_doorway_id": data.target_doorway_id,
        })
    except Exception:
        pass
    return {"status": "ok", "message": msg}


class CopyCloakingRequest(BaseModel):
    source_doorway_id: int  # 0 = auto best by CR
    target_doorway_id: int


@router.post("/campaign/{campaign_id}/copy-cloaking-from-winner")
async def campaign_copy_cloaking_from_winner(
    campaign_id: int,
    data: CopyCloakingRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Copy cloaking_rules (urgency, social_proof, exit_intent, faq, CTA) from best doorway to target."""
    from app.services.ai_optimizer import get_best_doorway_by_cr

    if not await _check_campaign_access(db, campaign_id, current_user.id):
        raise HTTPException(404, "Campaign not found")
    source_id = data.source_doorway_id
    if source_id == 0:
        source_id = await get_best_doorway_by_cr(db, campaign_id, current_user.id)
        if not source_id:
            raise HTTPException(400, "Нет дорвеев с достаточными данными (min 20 кликов)")
    r = await db.execute(
        select(Doorway)
        .join(Campaign)
        .where(
            Doorway.id.in_([source_id, data.target_doorway_id]),
            Doorway.campaign_id == campaign_id,
            Campaign.user_id == current_user.id,
        )
    )
    doorways = {d.id: d for d in r.scalars().all()}
    if source_id not in doorways or data.target_doorway_id not in doorways:
        raise HTTPException(404, "Doorway not found in campaign")
    src = doorways[source_id]
    tgt = doorways[data.target_doorway_id]
    tgt.cloaking_rules = dict(src.cloaking_rules or {})
    await db.commit()
    try:
        from app.services.webhook_service import notify_webhooks
        await notify_webhooks(db, current_user.id, "doorway.copy_cloaking", {
            "source_doorway_id": source_id,
            "target_doorway_id": data.target_doorway_id,
        })
    except Exception:
        pass
    return {"status": "ok", "message": f"Настройки скопированы с дорвея #{source_id}"}


@router.get("/anomalies")
async def get_anomalies(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(14, ge=7, le=30),
):
    """Detect anomalies: CR drops, zero conversions."""
    return await detect_anomalies(db, current_user.id, days=days)


class AffiliateRecommendRequest(BaseModel):
    keyword: str
    language: str = "ru"
    region: str = "RU"


@router.post("/affiliate-recommendations")
async def get_affiliate_recommendations(
    data: AffiliateRecommendRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """AI: recommend 3-5 affiliate networks for the niche."""
    from app.services.openai_service import openai_service
    from app.services.settings_helpers import get_user_openai_key

    key = (data.keyword or "").strip()
    if not key:
        raise HTTPException(400, "keyword required")
    user_key = await get_user_openai_key(db, current_user.id)
    if not openai_service.is_available(user_key):
        raise HTTPException(503, "OpenAI API key not configured in Settings")
    recs = await openai_service.generate_affiliate_recommendations(
        keyword=key,
        language=data.language,
        region=data.region,
        max_items=5,
        api_key_override=user_key,
    )
    return {"keyword": key, "recommendations": recs}
