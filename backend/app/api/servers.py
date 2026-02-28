"""Servers API."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.server import Server
from app.schemas.server import ServerCreate, ServerUpdate, ServerResponse, ServerTestConnection
from app.services.deploy import test_ssh_connection

router = APIRouter()


@router.post("/test-connection")
async def test_server_connection(
    data: ServerTestConnection,
    current_user: CurrentUser,
):
    """Test SSH connection with given params. Returns { ok: bool, message: str }."""
    ok, message = test_ssh_connection(
        host=data.host,
        port=data.port,
        user=data.user,
        auth_type=data.auth_type,
        auth_data=data.auth_data,
    )
    return {"ok": ok, "message": message}


@router.get("/", response_model=List[ServerResponse])
async def list_servers(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Server).order_by(Server.name))
    return result.scalars().all()


@router.post("/", response_model=ServerResponse)
async def create_server(
    data: ServerCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    server = Server(**data.model_dump())
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


@router.patch("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: int,
    data: ServerUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(server, k, v)
    await db.commit()
    await db.refresh(server)
    return server


@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    await db.delete(server)
    await db.commit()
    return None
