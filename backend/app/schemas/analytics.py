"""Analytics schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class DoorwayMetricsCreate(BaseModel):
    date: datetime
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0
    avg_position: float = 0
    conversions: int = 0
    revenue: float = 0


class DoorwayMetricsResponse(BaseModel):
    id: int
    doorway_id: int
    date: datetime
    impressions: int
    clicks: int
    ctr: float
    avg_position: float
    conversions: int
    revenue: float

    class Config:
        from_attributes = True


class PostbackRequest(BaseModel):
    sub_id: Optional[str] = None  # doorway_id or tracking_token
    payout: Optional[float] = None
    conversion: int = 1
    currency: Optional[str] = None


class AnalyticsSummary(BaseModel):
    total_impressions: int
    total_clicks: int
    total_conversions: int
    total_revenue: float
    doorway_count: int
    ctr_percent: float = 0
    cr_percent: float = 0


class DailyMetricsPoint(BaseModel):
    date: str  # YYYY-MM-DD
    impressions: int
    clicks: int
    conversions: int
    revenue: float
    ctr_percent: float = 0
    cr_percent: float = 0


class AnalyticsDailyResponse(BaseModel):
    series: list[DailyMetricsPoint]


class CampaignPerformance(BaseModel):
    campaign_id: int
    name: str
    impressions: int
    clicks: int
    conversions: int
    revenue: float
    ctr_percent: float = 0
    cr_percent: float = 0
    roi_per_click: float = 0
    doorway_count: int


class AnalyticsCampaignsResponse(BaseModel):
    campaigns: list[CampaignPerformance]
