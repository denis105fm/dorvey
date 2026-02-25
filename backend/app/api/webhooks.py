"""Webhooks API."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.webhook import Webhook

router = APIRouter()

EVENT_CHOICES = [
    "doorway.deployed",
    "doorway.conversion",
    "doorway.rollback",
    "doorway.anomaly",
    "doorway.auto_paused",
    "doorway.auto_fix",
    "doorway.copy_winner",
    "doorway.copy_cloaking",
    "campaign.created",
    "billing.near_limit",
    "billing.over_limit",
]


class WebhookCreate(BaseModel):
    url: str
    events: Optional[List[str]] = None
    is_active: bool = True


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    id: int
    url: str
    events: Optional[List[str]] = None
    is_active: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=List[WebhookResponse])
async def list_webhooks(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Webhook).where(Webhook.user_id == current_user.id))
    return list(r.scalars().all())


@router.post("/", response_model=WebhookResponse)
async def create_webhook(
    data: WebhookCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    w = Webhook(user_id=current_user.id, **data.model_dump())
    db.add(w)
    await db.commit()
    await db.refresh(w)
    return w


@router.patch("/{webhook_id}", response_model=WebhookResponse)
async def update_webhook(
    webhook_id: int,
    data: WebhookUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == current_user.id)
    )
    w = r.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Webhook not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(w, k, v)
    await db.commit()
    await db.refresh(w)
    return w


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    webhook_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Webhook).where(Webhook.id == webhook_id, Webhook.user_id == current_user.id)
    )
    w = r.scalar_one_or_none()
    if not w:
        raise HTTPException(status_code=404, detail="Webhook not found")
    await db.delete(w)
    await db.commit()
    return None
