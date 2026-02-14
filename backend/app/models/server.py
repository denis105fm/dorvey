"""Server model for deploy."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean

from app.core.database import Base


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=22)
    user = Column(String(100), nullable=False)
    auth_type = Column(String(20), default="ssh_key")
    auth_data = Column(String(500), nullable=True)
    path = Column(String(500), default="/var/www/html")
    ssl_auto = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
