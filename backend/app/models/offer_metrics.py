"""Offer metrics for ROI-based offer selection."""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.core.database import Base


class OfferMetrics(Base):
    __tablename__ = "offer_metrics"

    id = Column(Integer, primary_key=True, index=True)
    offer_id = Column(Integer, ForeignKey("offers.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0)

    offer = relationship("Offer", back_populates="metrics")
