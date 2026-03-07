"""Domain schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DomainBase(BaseModel):
    domain: str
    server_id: int
    campaign_id: Optional[int] = None
    status: str = "pending"


class DomainCreate(DomainBase):
    pass


class DomainUpdate(BaseModel):
    server_id: Optional[int] = None
    campaign_id: Optional[int] = None
    status: Optional[str] = None


class DomainResponse(DomainBase):
    id: int
    ssl_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
