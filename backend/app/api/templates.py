"""Templates API."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.template import Template
from app.schemas.template import TemplateCreate, TemplateUpdate, TemplateResponse

router = APIRouter()


@router.get("/", response_model=List[TemplateResponse])
async def list_templates(
    current_user: CurrentUser,
    type_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Template)
    if type_filter:
        q = q.where(Template.type == type_filter)
    q = q.order_by(Template.name)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/", response_model=TemplateResponse)
async def create_template(
    data: TemplateCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    t = Template(**data.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Template).where(Template.id == template_id))
    t = r.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return t


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    data: TemplateUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Template).where(Template.id == template_id))
    t = r.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    await db.commit()
    await db.refresh(t)
    return t


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(select(Template).where(Template.id == template_id))
    t = r.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.delete(t)
    await db.commit()
    return None
