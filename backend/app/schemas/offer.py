"""Offer schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class OfferBase(BaseModel):
    campaign_id: int
    url: str
    name: Optional[str] = None
    rate: Optional[str] = None
    amount: Optional[str] = None
    term: Optional[str] = None
    geo: Optional[str] = None
    device: Optional[str] = None
    priority: int = 0
    is_active: bool = True
    description: Optional[str] = None
    restrictions: Optional[str] = None
    recommendations: Optional[str] = None


class OfferCreate(OfferBase):
    pass


class OfferUpdate(BaseModel):
    url: Optional[str] = None
    name: Optional[str] = None
    rate: Optional[str] = None
    amount: Optional[str] = None
    term: Optional[str] = None
    geo: Optional[str] = None
    device: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None
    restrictions: Optional[str] = None
    recommendations: Optional[str] = None


class OfferResponse(OfferBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
