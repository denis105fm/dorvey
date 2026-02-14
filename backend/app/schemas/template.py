"""Template schemas."""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class TemplateBase(BaseModel):
    name: str
    type: str = "page"
    content: Optional[str] = None
    variables: Optional[list[str]] = None


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    content: Optional[str] = None
    variables: Optional[list[str]] = None


class TemplateResponse(TemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
