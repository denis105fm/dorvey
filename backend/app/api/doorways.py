"""Doorways API."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.doorway import Doorway
from app.models.campaign import Campaign
from app.models.doorway import DoorwayVersion
from app.schemas.doorway import (
    DoorwayCreate,
    DoorwayUpdate,
    DoorwayResponse,
    DoorwayGenerateRequest,
    DoorwayGenerateResponse,
    DoorwayBatchGenerateRequest,
    DoorwayBatchGenerateResponse,
)
from app.services.generator import generate_doorway

router = APIRouter()


async def _check_campaign_access(db: AsyncSession, campaign_id: int, user_id: int) -> bool:
    result = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
    )
    return result.scalar_one_or_none() is not None


@router.get("/", response_model=List[DoorwayResponse])
async def list_doorways(
    current_user: CurrentUser,
    campaign_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Doorway)
    if campaign_id:
        ok = await _check_campaign_access(db, campaign_id, current_user.id)
        if not ok:
            raise HTTPException(status_code=404, detail="Campaign not found")
        q = q.where(Doorway.campaign_id == campaign_id)
    else:
        q = q.join(Campaign).where(Campaign.user_id == current_user.id)
    q = q.order_by(Doorway.created_at.desc())
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/generate", response_model=DoorwayGenerateResponse)
async def generate_doorway_content(
    data: DoorwayGenerateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ok = await _check_campaign_access(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    try:
        result = await generate_doorway(
            db,
            campaign_id=data.campaign_id,
            domain_id=data.domain_id,
            keyword=data.keyword,
            path=data.path,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    doorway_id = None
    if data.save and result:
        dw = Doorway(
            campaign_id=data.campaign_id,
            domain_id=data.domain_id,
            path=data.path,
            title=result.get("title"),
            content=result.get("content"),
            meta_description=result.get("meta_description"),
            status="draft",
        )
        db.add(dw)
        await db.commit()
        await db.refresh(dw)
        doorway_id = dw.id
        # Save version for rollback
        snap = {
            "title": dw.title,
            "content": dw.content,
            "meta_description": dw.meta_description,
        }
        ver = DoorwayVersion(doorway_id=dw.id, content_snapshot=snap)
        db.add(ver)
        await db.commit()
    return DoorwayGenerateResponse(
        title=result.get("title", ""),
        meta_description=result.get("meta_description", ""),
        content=result.get("content", ""),
        html=result.get("html", ""),
        doorway_id=doorway_id,
        validation_violations=result.get("validation_violations"),
    )


@router.post("/generate-batch", response_model=DoorwayBatchGenerateResponse)
async def generate_batch(
    data: DoorwayBatchGenerateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    results = []
    created = 0
    for item in data.items[:50]:  # limit 50 per request
        ok = await _check_campaign_access(db, item.campaign_id, current_user.id)
        if not ok:
            results.append({"keyword": item.keyword, "status": "error", "error": "Campaign not found"})
            continue
        try:
            gen_result = await generate_doorway(
                db,
                campaign_id=item.campaign_id,
                domain_id=item.domain_id,
                keyword=item.keyword,
                path=item.path,
            )
        except ValueError as e:
            results.append({"keyword": item.keyword, "status": "error", "error": str(e)})
            continue
        doorway_id = None
        try:
            dw = Doorway(
                campaign_id=item.campaign_id,
                domain_id=item.domain_id,
                path=item.path,
                title=gen_result.get("title"),
                content=gen_result.get("content"),
                meta_description=gen_result.get("meta_description"),
                status="draft",
            )
            db.add(dw)
            await db.flush()
            doorway_id = dw.id
            ver = DoorwayVersion(doorway_id=dw.id, content_snapshot={
                "title": dw.title, "content": dw.content, "meta_description": dw.meta_description,
            })
            db.add(ver)
            created += 1
            results.append({"keyword": item.keyword, "status": "ok", "doorway_id": doorway_id})
        except Exception as ex:
            results.append({"keyword": item.keyword, "status": "error", "error": str(ex)})
    await db.commit()
    return DoorwayBatchGenerateResponse(created=created, results=results)


@router.post("/", response_model=DoorwayResponse)
async def create_doorway(
    data: DoorwayCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ok = await _check_campaign_access(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    doorway = Doorway(**data.model_dump())
    db.add(doorway)
    await db.commit()
    await db.refresh(doorway)
    return doorway


@router.get("/{doorway_id}/quality-check")
async def doorway_quality_check(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Pre-deploy content quality check (anti-detection)."""
    from app.services.anti_detection import check_content_quality

    result = await db.execute(
        select(Doorway)
        .join(Campaign)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    doorway = result.scalar_one_or_none()
    if not doorway:
        raise HTTPException(status_code=404, detail="Doorway not found")
    keyword = None
    # Try to get keyword from path or campaign keywords
    from app.models.keyword import Keyword
    kw_r = await db.execute(
        select(Keyword.keyword).where(Keyword.campaign_id == doorway.campaign_id).limit(1)
    )
    kw_row = kw_r.first()
    if kw_row:
        keyword = kw_row[0]
    r = check_content_quality(
        title=doorway.title or "",
        meta_description=doorway.meta_description or "",
        content=doorway.content or "",
        keyword=keyword,
    )
    return {"ok": r.ok, "errors": r.errors, "warnings": r.warnings}


@router.get("/{doorway_id}", response_model=DoorwayResponse)
async def get_doorway(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Doorway)
        .join(Campaign)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    doorway = result.scalar_one_or_none()
    if not doorway:
        raise HTTPException(status_code=404, detail="Doorway not found")
    return doorway


@router.patch("/{doorway_id}", response_model=DoorwayResponse)
async def update_doorway(
    doorway_id: int,
    data: DoorwayUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Doorway)
        .join(Campaign)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    doorway = result.scalar_one_or_none()
    if not doorway:
        raise HTTPException(status_code=404, detail="Doorway not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(doorway, k, v)
    await db.commit()
    await db.refresh(doorway)
    return doorway


@router.delete("/{doorway_id}", status_code=204)
async def delete_doorway(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Doorway)
        .join(Campaign)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    doorway = result.scalar_one_or_none()
    if not doorway:
        raise HTTPException(status_code=404, detail="Doorway not found")
    await db.delete(doorway)
    await db.commit()
    return None
