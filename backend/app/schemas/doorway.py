"""Doorway schemas."""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel


class DoorwayBase(BaseModel):
    campaign_id: int
    domain_id: int
    path: str = "/"
    title: Optional[str] = None
    content: Optional[str] = None
    meta_description: Optional[str] = None
    cloaking_rules: Optional[dict[str, Any]] = None
    content_variants: Optional[list[dict[str, Any]]] = None
    status: str = "draft"


class DoorwayCreate(DoorwayBase):
    pass


class DoorwayUpdate(BaseModel):
    path: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    meta_description: Optional[str] = None
    cloaking_rules: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class DoorwayBatchItem(BaseModel):
    campaign_id: int
    domain_id: int
    keyword: str
    path: str = "/"


class DoorwayBatchGenerateRequest(BaseModel):
    items: list[DoorwayBatchItem]


class DoorwayBatchGenerateResponse(BaseModel):
    created: int
    results: list[dict]


class DoorwayGenerateRequest(BaseModel):
    campaign_id: int
    domain_id: int
    keyword: str
    path: str = "/"
    save: bool = True  # Create doorway in DB after generation
    generate_faq: bool = False  # Generate 3-5 Q&A for FAQ/PAA schema


class DoorwayGenerateResponse(BaseModel):
    title: str
    meta_description: str
    content: str
    html: str
    doorway_id: Optional[int] = None  # If save=True
    validation_violations: Optional[list[str]] = None
    faq_qa: Optional[list[dict[str, str]]] = None  # [{question, answer}, ...]


class DoorwayResponse(DoorwayBase):
    id: int
    deployed_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
