"""Offers API - geo/device routing."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.offer import Offer
from app.models.campaign import Campaign
from app.schemas.offer import OfferCreate, OfferUpdate, OfferResponse

router = APIRouter()


async def _check(db: AsyncSession, campaign_id: int, user_id: int) -> bool:
    r = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
    )
    return r.scalar_one_or_none() is not None


@router.get("/", response_model=List[OfferResponse])
async def list_offers(current_user: CurrentUser, campaign_id: int, db: AsyncSession = Depends(get_db)):
    if not await _check(db, campaign_id, current_user.id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    r = await db.execute(select(Offer).where(Offer.campaign_id == campaign_id).order_by(Offer.priority.desc()))
    return list(r.scalars().all())


@router.post("/", response_model=OfferResponse)
async def create_offer(data: OfferCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    if not await _check(db, data.campaign_id, current_user.id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    o = Offer(**data.model_dump())
    db.add(o)
    await db.commit()
    await db.refresh(o)
    return o


@router.patch("/{offer_id}", response_model=OfferResponse)
async def update_offer(offer_id: int, data: OfferUpdate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Offer).join(Campaign).where(Offer.id == offer_id, Campaign.user_id == current_user.id))
    o = r.scalar_one_or_none()
    if not o:
        raise HTTPException(status_code=404, detail="Offer not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    await db.commit()
    await db.refresh(o)
    return o


@router.delete("/{offer_id}", status_code=204)
async def delete_offer(offer_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Offer).join(Campaign).where(Offer.id == offer_id, Campaign.user_id == current_user.id))
    o = r.scalar_one_or_none()
    if not o:
        raise HTTPException(status_code=404, detail="Offer not found")
    await db.delete(o)
    await db.commit()
    return None
