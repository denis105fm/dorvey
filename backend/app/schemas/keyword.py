"""Keyword schemas."""

from typing import Optional

from pydantic import BaseModel


class KeywordBase(BaseModel):
    campaign_id: int
    keyword: str
    cluster_id: Optional[int] = None
    volume: int = 0
    region: Optional[str] = None
    source: Optional[str] = None


class KeywordCreate(KeywordBase):
    pass


class KeywordBulkCreate(BaseModel):
    campaign_id: int
    keywords: list[str]
    volume: int = 0
    region: Optional[str] = None
    source: Optional[str] = None


class KeywordSuggestItem(BaseModel):
    keyword: str
    volume: int
    cpc: float


class KeywordSuggestFromExternalRequest(BaseModel):
    campaign_id: int
    seed: str
    country: str = "RU"
    limit: int = 50


class KeywordSuggestFromExternalResponse(BaseModel):
    keywords: list[KeywordSuggestItem]
    source: str = "dataforseo"
    hint: Optional[str] = None  # сообщение об ошибке/подсказка, если ключей 0


class KeywordBulkImportFromSuggest(BaseModel):
    campaign_id: int
    items: list[KeywordSuggestItem]
    region: Optional[str] = None
    source: Optional[str] = None  # dataforseo | fetchserp — сохраняется в Keyword.source


class KeywordResponse(KeywordBase):
    id: int

    class Config:
        from_attributes = True
