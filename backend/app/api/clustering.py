"""Keyword clustering API."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.keyword import Keyword
from app.models.campaign import Campaign
from app.services.clustering import cluster_keywords

router = APIRouter()


class ClusterRequest(BaseModel):
    campaign_id: int
    n_clusters: int = 5


@router.post("/cluster")
async def run_clustering(
    data: ClusterRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Campaign).where(Campaign.id == data.campaign_id, Campaign.user_id == current_user.id)
    )
    if not r.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Campaign not found")
    r2 = await db.execute(
        select(Keyword).where(Keyword.campaign_id == data.campaign_id).order_by(Keyword.id)
    )
    kw_list = list(r2.scalars().all())
    keywords = [k.keyword for k in kw_list]
    labels = cluster_keywords(keywords, data.n_clusters)
    for i, kw in enumerate(kw_list):
        if i < len(labels):
            kw.cluster_id = labels[i]
    await db.commit()
    return {"status": "ok", "clustered": len(kw_list)}
