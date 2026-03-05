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
    layout_index: Optional[int] = None
    target_geo: Optional[str] = None


class DoorwayCreate(DoorwayBase):
    pass


class DoorwayUpdate(BaseModel):
    path: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    meta_description: Optional[str] = None
    cloaking_rules: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    layout_index: Optional[int] = None
    quiz_enabled: Optional[bool] = None  # Toggle quiz block visibility (merged into cloaking_rules.quiz.enabled)


class DoorwayBatchItem(BaseModel):
    campaign_id: int
    domain_id: int
    keyword: str
    path: str = "/"
    target_geo: Optional[str] = None
    target_geos: Optional[list[str]] = None  # if len>1: create one doorway per geo


class DoorwayBatchGenerateRequest(BaseModel):
    items: list[DoorwayBatchItem]
    generate_faq: bool = False
    generate_quiz: bool = False
    target_geos: Optional[list[str]] = None  # applied to all items when set (overrides item target_geos if not set per item)


class DoorwayBatchGenerateResponse(BaseModel):
    created: int
    results: list[dict]


class DoorwayGenerateRequest(BaseModel):
    campaign_id: int
    domain_id: int
    keyword: str
    path: str = "/"
    save: bool = True
    generate_faq: bool = False
    generate_quiz: bool = False
    target_geo: Optional[str] = None
    target_geos: Optional[list[str]] = None  # if len>1: create one doorway per geo (path = /{lang}/{slug})


class DoorwayGenerateResponse(BaseModel):
    title: str
    meta_description: str
    content: str
    html: str
    doorway_id: Optional[int] = None
    created_count: int = 1  # when target_geos: number of doorways created
    validation_violations: Optional[list[str]] = None
    faq_qa: Optional[list[dict[str, str]]] = None
    quiz_questions: Optional[list[dict]] = None


class DoorwayResponse(DoorwayBase):
    id: int
    deployed_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None
    created_at: datetime
    pause_reason: Optional[str] = None

    class Config:
        from_attributes = True
