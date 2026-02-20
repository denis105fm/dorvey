"""Doorway and related models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Doorway(Base):
    __tablename__ = "doorways"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    domain_id = Column(Integer, ForeignKey("domains.id"), nullable=False)
    path = Column(String(500), default="/")  # URL path
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    meta_description = Column(String(500), nullable=True)
    cloaking_rules = Column(JSONB, default=dict)
    content_variants = Column(JSONB, default=list)  # [{title, content, meta_description}, ...]
    status = Column(String(30), default="draft")  # draft, deployed, indexed, optimizing, paused
    pause_reason = Column(String(500), nullable=True)  # причина авто-паузы (например: мало выручки)
    created_at = Column(DateTime, default=datetime.utcnow)
    deployed_at = Column(DateTime, nullable=True)
    indexed_at = Column(DateTime, nullable=True)

    campaign = relationship("Campaign", back_populates="doorways")
    domain = relationship("Domain", back_populates="doorways")
    versions = relationship("DoorwayVersion", back_populates="doorway", order_by="DoorwayVersion.created_at.desc()")
    metrics = relationship("DoorwayMetrics", back_populates="doorway")


class DoorwayVersion(Base):
    __tablename__ = "doorway_versions"

    id = Column(Integer, primary_key=True, index=True)
    doorway_id = Column(Integer, ForeignKey("doorways.id"), nullable=False)
    content_snapshot = Column(JSONB, nullable=False)  # title, content, meta_description
    created_at = Column(DateTime, default=datetime.utcnow)

    doorway = relationship("Doorway", back_populates="versions")


class DoorwayMetrics(Base):
    __tablename__ = "doorway_metrics"

    id = Column(Integer, primary_key=True, index=True)
    doorway_id = Column(Integer, ForeignKey("doorways.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    ctr = Column(Float, default=0)
    avg_position = Column(Float, default=0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0)

    doorway = relationship("Doorway", back_populates="metrics")
