"""A/B variant model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base


class DoorwayABVariant(Base):
    __tablename__ = "doorway_ab_variants"

    id = Column(Integer, primary_key=True, index=True)
    doorway_id = Column(Integer, ForeignKey("doorways.id"), nullable=False)
    variant = Column(String(10), nullable=False)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    meta_description = Column(String(500), nullable=True)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    is_winner = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
