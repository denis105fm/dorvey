"""Servers API."""

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.server import Server
from app.models.server_metric import ServerMetric
from app.schemas.server import ServerCreate, ServerUpdate, ServerResponse, ServerTestConnection
from app.services.deploy import test_ssh_connection
from app.services.server_metrics import collect_metrics

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


@router.get("/{server_id}/metrics")
async def get_server_metrics(
    server_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    period: Optional[str] = Query("24h", description="1h, 24h, 7d"),
):
    """Return metrics for the server. period: 1h, 24h, 7d."""
    result = await db.execute(select(Server).where(Server.id == server_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Server not found")
    since = datetime.utcnow()
    if period == "1h":
        since -= timedelta(hours=1)
    elif period == "7d":
        since -= timedelta(days=7)
    else:
        since -= timedelta(hours=24)
    r = await db.execute(
        select(ServerMetric)
        .where(and_(ServerMetric.server_id == server_id, ServerMetric.created_at >= since))
        .order_by(ServerMetric.created_at.asc())
    )
    rows = r.scalars().all()
    return {
        "server_id": server_id,
        "period": period,
        "metrics": [
            {
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "load_1": m.load_1,
                "load_5": m.load_5,
                "load_15": m.load_15,
                "mem_total_kb": m.mem_total_kb,
                "mem_available_kb": m.mem_available_kb,
                "disk_total_kb": m.disk_total_kb,
                "disk_used_kb": m.disk_used_kb,
                "nproc": m.nproc,
            }
            for m in rows
        ],
    }


@router.post("/{server_id}/metrics/collect")
async def collect_server_metrics_now(
    server_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Collect metrics right now via SSH (real-time snapshot). Saves to DB and returns the new metric."""
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    data = collect_metrics(server)
    if not data:
        raise HTTPException(status_code=503, detail="Could not collect metrics (SSH error or timeout)")
    m = ServerMetric(
        server_id=server_id,
        created_at=datetime.utcnow(),
        load_1=data.get("load_1"),
        load_5=data.get("load_5"),
        load_15=data.get("load_15"),
        mem_total_kb=data.get("mem_total_kb"),
        mem_available_kb=data.get("mem_available_kb"),
        disk_total_kb=data.get("disk_total_kb"),
        disk_used_kb=data.get("disk_used_kb"),
        nproc=data.get("nproc"),
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return {
        "server_id": server_id,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "load_1": m.load_1,
        "load_5": m.load_5,
        "load_15": m.load_15,
        "mem_total_kb": m.mem_total_kb,
        "mem_available_kb": m.mem_available_kb,
        "disk_total_kb": m.disk_total_kb,
        "disk_used_kb": m.disk_used_kb,
        "nproc": m.nproc,
    }


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
