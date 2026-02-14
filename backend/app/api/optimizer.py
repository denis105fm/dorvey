"""AI Optimizer API."""

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentUser
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.doorway import Doorway
from app.models.campaign import Campaign

from app.services.ai_optimizer import get_recommendations, rollback_doorway, get_ab_winner, apply_recommendation
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


@router.get("/anomalies")
async def get_anomalies(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    days: int = Query(14, ge=7, le=30),
):
    """Detect anomalies: CR drops, zero conversions."""
    return await detect_anomalies(db, current_user.id, days=days)
