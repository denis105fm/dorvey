"""Copy winning doorways."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.doorway import Doorway, DoorwayVersion
from app.models.campaign import Campaign
from app.models.domain import Domain
from pydantic import BaseModel

router = APIRouter()


class CopyWinnerRequest(BaseModel):
    doorway_id: int
    new_domain_id: int
    new_keyword: str
    new_path: str = "/"


@router.post("/winner")
async def copy_winner(
    data: CopyWinnerRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Doorway)
        .join(Campaign)
        .where(Doorway.id == data.doorway_id, Campaign.user_id == current_user.id)
    )
    src = r.scalar_one_or_none()
    if not src:
        raise HTTPException(status_code=404, detail="Doorway not found")
    r2 = await db.execute(select(Domain).where(Domain.id == data.new_domain_id))
    if not r2.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Domain not found")
    new_dw = Doorway(
        campaign_id=src.campaign_id,
        domain_id=data.new_domain_id,
        path=data.new_path or "/",
        title=src.title or f"{data.new_keyword} | Лучшие предложения",
        content=src.content,
        meta_description=src.meta_description,
        status="draft",
    )
    db.add(new_dw)
    await db.flush()
    db.add(DoorwayVersion(
        doorway_id=new_dw.id,
        content_snapshot={"title": new_dw.title, "content": new_dw.content, "meta_description": new_dw.meta_description},
    ))
    await db.commit()
    return {"status": "ok", "doorway_id": new_dw.id}
