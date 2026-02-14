"""Keywords API (semantic module)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.keyword import Keyword
from app.models.campaign import Campaign
from app.schemas.keyword import KeywordCreate, KeywordBulkCreate, KeywordResponse

router = APIRouter()


async def _check_campaign(db: AsyncSession, campaign_id: int, user_id: int) -> bool:
    r = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
    )
    return r.scalar_one_or_none() is not None


@router.get("/", response_model=List[KeywordResponse])
async def list_keywords(
    current_user: CurrentUser,
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
):
    ok = await _check_campaign(db, campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    r = await db.execute(
        select(Keyword).where(Keyword.campaign_id == campaign_id).order_by(Keyword.keyword)
    )
    return r.scalars().all()


@router.post("/", response_model=KeywordResponse)
async def create_keyword(
    data: KeywordCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ok = await _check_campaign(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    k = Keyword(**data.model_dump())
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


@router.post("/bulk", response_model=List[KeywordResponse])
async def bulk_create_keywords(
    data: KeywordBulkCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ok = await _check_campaign(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    created = []
    for kw in data.keywords:
        k = Keyword(
            campaign_id=data.campaign_id,
            keyword=kw.strip(),
            volume=data.volume,
        )
        db.add(k)
        await db.flush()
        created.append(k)
    await db.commit()
    for k in created:
        await db.refresh(k)
    return created


@router.delete("/{keyword_id}", status_code=204)
async def delete_keyword(
    keyword_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Keyword).join(Campaign).where(
            Keyword.id == keyword_id, Campaign.user_id == current_user.id
        )
    )
    k = r.scalar_one_or_none()
    if not k:
        raise HTTPException(status_code=404, detail="Keyword not found")
    await db.delete(k)
    await db.commit()
    return None
