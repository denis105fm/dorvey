"""Domains API."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.domain import Domain
from app.schemas.domain import DomainCreate, DomainUpdate, DomainResponse

router = APIRouter()


@router.get("/", response_model=List[DomainResponse])
async def list_domains(
    current_user: CurrentUser,
    campaign_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Domain)
    if campaign_id:
        q = q.where(Domain.campaign_id == campaign_id)
    q = q.order_by(Domain.domain)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=DomainResponse)
async def create_domain(
    data: DomainCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Domain).where(Domain.domain == data.domain))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Domain already exists")
    domain = Domain(**data.model_dump())
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return domain


@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain


@router.patch("/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: int,
    data: DomainUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(domain, k, v)
    await db.commit()
    await db.refresh(domain)
    return domain


@router.delete("/{domain_id}", status_code=204)
async def delete_domain(
    domain_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Domain).where(Domain.id == domain_id))
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    await db.delete(domain)
    await db.commit()
    return None
