"""Campaign schemas."""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class CampaignBase(BaseModel):
    name: str
    affiliate_url: Optional[str] = None
    affiliate_rules: Optional[dict[str, Any]] = None
    language: str = "ru"
    locale: str = "ru-RU"
    region: str = "RU"
    currency: str = "RUB"
    status: str = "active"


class CampaignCreate(CampaignBase):
    pass


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    affiliate_url: Optional[str] = None
    affiliate_rules: Optional[dict[str, Any]] = None
    language: Optional[str] = None
    locale: Optional[str] = None
    region: Optional[str] = None
    currency: Optional[str] = None
    status: Optional[str] = None


class CampaignResponse(CampaignBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
