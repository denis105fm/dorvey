"""Keyword schemas."""

from typing import Optional

from pydantic import BaseModel


class KeywordBase(BaseModel):
    campaign_id: int
    keyword: str
    cluster_id: Optional[int] = None
    volume: int = 0


class KeywordCreate(KeywordBase):
    pass


class KeywordBulkCreate(BaseModel):
    campaign_id: int
    keywords: list[str]
    volume: int = 0


class KeywordResponse(KeywordBase):
    id: int

    class Config:
        from_attributes = True
