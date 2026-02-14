"""SEO API: internal linking, cannibalization, domain suggestions."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.doorway import Doorway
from app.models.campaign import Campaign

from app.services.seo_tools import get_internal_links_suggestions, detect_cannibalization, suggest_domains

router = APIRouter()


async def _check_doorway(db, doorway_id: int, user_id: int):
    r = await db.execute(select(Doorway).join(Campaign).where(Doorway.id == doorway_id, Campaign.user_id == user_id))
    return r.scalar_one_or_none()


async def _check_campaign(db, campaign_id: int, user_id: int):
    r = await db.execute(select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id))
    return r.scalar_one_or_none()


@router.get("/internal-links/{doorway_id}")
async def get_internal_links(doorway_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    dw = await _check_doorway(db, doorway_id, current_user.id)
    if not dw:
        raise HTTPException(404, "Doorway not found")
    return await get_internal_links_suggestions(db, doorway_id, dw.campaign_id)


@router.get("/cannibalization/{campaign_id}")
async def get_cannibalization(campaign_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    if not await _check_campaign(db, campaign_id, current_user.id):
        raise HTTPException(404, "Campaign not found")
    return await detect_cannibalization(db, campaign_id, current_user.id)


@router.get("/domains/suggest")
async def get_domain_suggestions(current_user: CurrentUser, keyword: str = Query(...), region: str = Query("RU"), count: int = Query(5, le=10)):
    return await suggest_domains(keyword, region, count)
