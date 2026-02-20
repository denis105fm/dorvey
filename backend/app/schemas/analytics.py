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
    # Доля дорвеев с трафиком (>= min_clicks), которые приносят прибыль (revenue > 0)
    profitable_doorways_percent: float = 0
    profitable_doorways_count: int = 0
    doorways_with_traffic_count: int = 0


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


class DoorwayProfitMetric(BaseModel):
    doorway_id: int
    clicks: int
    revenue: float
    conversions: int
    profit_status: str  # "profitable" | "unprofitable" | "no_traffic"
    health_score: int  # 0-100
    min_clicks_used: int
    profit_probability: str = "low"  # "low" | "medium" | "high" — прогноз вероятности прибыли
    campaign_id: int | None = None
    benchmark_cr: float | None = None  # средний CR по кампании (бенчмарк)
    benchmark_roi: float | None = None  # средний revenue/click по кампании
    above_benchmark_cr: bool | None = None
    above_benchmark_roi: bool | None = None


class AnalyticsDoorwaysMetricsResponse(BaseModel):
    doorways: list[DoorwayProfitMetric]
    min_clicks_used: int
    external_signals_by_country: dict | None = None  # гео -> { news, seasonality, sources_used }
