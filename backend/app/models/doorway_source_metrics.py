"""Doorway metrics by traffic source (utm_source) for ROI by source."""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Float, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class DoorwaySourceMetrics(Base):
    __tablename__ = "doorway_source_metrics"

    id = Column(Integer, primary_key=True, index=True)
    doorway_id = Column(Integer, ForeignKey("doorways.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    source = Column(String(32), nullable=False)  # e.g. "google", "fb", "direct"
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0)

    doorway = relationship("Doorway", back_populates="source_metrics")
