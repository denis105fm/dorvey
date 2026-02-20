"""Visitor events and push subscriptions for remarketing."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class VisitorEvent(Base):
    __tablename__ = "visitor_events"

    id = Column(Integer, primary_key=True, index=True)
    visitor_id = Column(String(64), nullable=False, index=True)
    doorway_id = Column(Integer, ForeignKey("doorways.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(20), nullable=False)  # visit, click, push_subscribe
    meta = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    visitor_id = Column(String(64), nullable=False, index=True)
    doorway_id = Column(Integer, ForeignKey("doorways.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    subscription = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EmailLead(Base):
    __tablename__ = "email_leads"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    visitor_id = Column(String(64), nullable=True, index=True)
    doorway_id = Column(Integer, ForeignKey("doorways.id", ondelete="CASCADE"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
