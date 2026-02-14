"""Offer schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OfferBase(BaseModel):
    campaign_id: int
    url: str
    geo: Optional[str] = None
    device: Optional[str] = None
    priority: int = 0
    is_active: bool = True


class OfferCreate(OfferBase):
    pass


class OfferUpdate(BaseModel):
    url: Optional[str] = None
    geo: Optional[str] = None
    device: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class OfferResponse(OfferBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
