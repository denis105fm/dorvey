"""Campaign model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    affiliate_url = Column(Text, nullable=True)
    affiliate_rules = Column(JSONB, default=dict)
    language = Column(String(10), default="ru")
    locale = Column(String(10), default="ru-RU")
    region = Column(String(10), default="RU")
    currency = Column(String(5), default="RUB")
    status = Column(String(20), default="active")
    is_black = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="campaigns")
    doorways = relationship("Doorway", back_populates="campaign")
    domains = relationship("Domain", back_populates="campaign")
    keywords = relationship("Keyword", back_populates="campaign")
    offers = relationship("Offer", back_populates="campaign")
