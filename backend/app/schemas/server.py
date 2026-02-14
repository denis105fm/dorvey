"""Server schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ServerBase(BaseModel):
    name: str
    host: str
    port: int = 22
    user: str
    auth_type: str = "ssh_key"
    path: str = "/var/www/html"
    ssl_auto: bool = True


class ServerCreate(ServerBase):
    auth_data: Optional[str] = None


class ServerUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    auth_type: Optional[str] = None
    auth_data: Optional[str] = None
    path: Optional[str] = None
    ssl_auto: Optional[bool] = None


class ServerResponse(ServerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        # Exclude auth_data from response for security
