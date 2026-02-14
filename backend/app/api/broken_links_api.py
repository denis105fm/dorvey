"""Broken links API."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.doorway import Doorway
from app.models.campaign import Campaign

from app.services.broken_links import find_broken_links, repair_broken_links_in_content

router = APIRouter()


async def _check(db, doorway_id: int, user_id: int):
    r = await db.execute(select(Doorway).join(Campaign).where(Doorway.id == doorway_id, Campaign.user_id == user_id))
    return r.scalar_one_or_none()


@router.get("/doorway/{doorway_id}")
async def check_broken_links(doorway_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    dw = await _check(db, doorway_id, current_user.id)
    if not dw:
        raise HTTPException(404, "Doorway not found")
    return await find_broken_links(db, doorway_id, dw.content or "")


class RepairRequest(BaseModel):
    broken_urls: list[str]
    replacement: str = "#"


@router.post("/doorway/{doorway_id}/repair")
async def repair_links(doorway_id: int, data: RepairRequest, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    dw = await _check(db, doorway_id, current_user.id)
    if not dw:
        raise HTTPException(404, "Doorway not found")
    new_content = repair_broken_links_in_content(dw.content or "", data.broken_urls, data.replacement)
    dw.content = new_content
    await db.commit()
    return {"status": "ok", "repaired": len(data.broken_urls)}
