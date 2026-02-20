"""Offer model for geo/device routing."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base


class Offer(Base):
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    url = Column(Text, nullable=False)
    name = Column(String(255), nullable=True)
    rate = Column(String(50), nullable=True)
    amount = Column(String(50), nullable=True)
    term = Column(String(50), nullable=True)
    geo = Column(String(20), nullable=True)
    device = Column(String(20), nullable=True)
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    campaign = relationship("Campaign", back_populates="offers")
