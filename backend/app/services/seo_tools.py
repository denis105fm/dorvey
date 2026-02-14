"""SEO tools: internal linking, cannibalization, domain suggestions."""
import re
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.doorway import Doorway
from app.models.domain import Domain
from app.models.campaign import Campaign


async def get_internal_links_suggestions(db: AsyncSession, doorway_id: int, campaign_id: int, max_links: int = 3) -> List[dict]:
    r = await db.execute(
        select(Doorway, Domain).join(Domain, Doorway.domain_id == Domain.id).join(Campaign, Doorway.campaign_id == Campaign.id).where(
            Doorway.campaign_id == campaign_id, Doorway.id != doorway_id,
            Doorway.status.in_(["deployed", "indexed"])))
    rows = r.all()
    out = []
    for dw, dom in rows[:max_links]:
        path = (dw.path or "/").strip() or "/"
        out.append({"doorway_id": dw.id, "domain": dom.domain, "path": path, "url": f"https://{dom.domain}{path}", "title": dw.title or "", "anchor": dw.title or path})
    return out


async def detect_cannibalization(db: AsyncSession, campaign_id: int, user_id: int) -> List[dict]:
    r = await db.execute(select(Doorway.id, Doorway.title, Doorway.path).join(Campaign).where(Doorway.campaign_id == campaign_id, Campaign.user_id == user_id))
    kw_to_dw = {}
    for dw_id, title, path in r.all():
        kws = (re.findall(r"\w+", (title or "").lower())[:5] if title else []) + ([path.strip("/").replace("-", " ").lower()] if path and path != "/" else [])
        for kw in kws:
            if len(kw) > 2:
                kw_to_dw.setdefault(kw, []).append(dw_id)
    return [{"keyword": k, "doorway_ids": list(set(v)), "count": len(set(v)), "suggestion": "Объедините или разнесите"} for k, v in kw_to_dw.items() if len(set(v)) >= 2]


async def suggest_domains(keyword: str, region: str = "RU", count: int = 5) -> List[dict]:
    b = keyword.lower().replace(" ", "-")
    return [{"domain": f"{b}.ru", "available": None}, {"domain": f"{b.replace('-','')}.ru", "available": None}][:count]
