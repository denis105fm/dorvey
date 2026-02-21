"""Keyword model for semantic."""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class Keyword(Base):
    __tablename__ = "keywords"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    keyword = Column(String(500), nullable=False)
    cluster_id = Column(Integer, nullable=True)
    volume = Column(Integer, default=0)
    region = Column(String(10), nullable=True)
    source = Column(String(50), nullable=True)

    campaign = relationship("Campaign", back_populates="keywords")
