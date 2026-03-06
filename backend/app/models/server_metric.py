"""Server metrics (VPS monitoring)."""

from datetime import datetime
from sqlalchemy import Column, Integer, BigInteger, Float, DateTime, ForeignKey

from app.core.database import Base


class ServerMetric(Base):
    __tablename__ = "server_metrics"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    load_1 = Column(Float, nullable=True)
    load_5 = Column(Float, nullable=True)
    load_15 = Column(Float, nullable=True)
    mem_total_kb = Column(BigInteger, nullable=True)
    mem_available_kb = Column(BigInteger, nullable=True)
    disk_total_kb = Column(BigInteger, nullable=True)
    disk_used_kb = Column(BigInteger, nullable=True)
    nproc = Column(Integer, nullable=True)
