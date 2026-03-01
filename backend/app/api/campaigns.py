"""Campaigns API."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.campaign import Campaign
from app.models.offer import Offer
from app.models.domain import Domain
from app.models.keyword import Keyword
from app.models.doorway import Doorway, DoorwayVersion
from app.schemas.campaign import CampaignCreate, CampaignUpdate, CampaignResponse

router = APIRouter()


@router.get("/", response_model=List[CampaignResponse])
async def list_campaigns(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Campaign).where(Campaign.user_id == current_user.id).order_by(Campaign.created_at.desc())
    )
    return result.scalars().all()


DEFAULT_AFFILIATE_RULES = {
    "ai": {"auto_rollback_on_cr_drop": True, "rollback_threshold_percent": 15},
    "offers": {"auto_switch_on_cr_drop": False},
}


@router.post("/", response_model=CampaignResponse)
async def create_campaign(
    data: CampaignCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    dump = data.model_dump()
    if dump.get("affiliate_rules") is None:
        dump["affiliate_rules"] = DEFAULT_AFFILIATE_RULES
    campaign = Campaign(user_id=current_user.id, **dump)
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    try:
        from app.api.billing import notify_billing_limits_if_needed
        await notify_billing_limits_if_needed(db, current_user.id)
    except Exception:
        pass
    return campaign


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: int,
    data: CampaignUpdate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(campaign, k, v)
    await db.commit()
    await db.refresh(campaign)
    return campaign


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id,
        )
    )
    campaign = result.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await db.delete(campaign)
    await db.commit()
    return None


class OfferInput(BaseModel):
    url: str
    geo: Optional[str] = None
    name: Optional[str] = None


class AutoCreateFromOffersRequest(BaseModel):
    name: str
    offers: List[OfferInput]
    seed_keywords: List[str]
    limit_keywords: int = 50
    domain_id: Optional[int] = None
    create_doorways: bool = False


@router.post("/auto-create-from-offers")
async def auto_create_campaign_from_offers(
    data: AutoCreateFromOffersRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Авто-создание кампании из офферов: создать кампанию → добавить офферы →
    сгенерировать ключи по гео через выбранный провайдер → добавить ключи в кампанию →
    опционально создать дорвеи по топу ключей (нужен domain_id).
    """
    if not (data.offers and data.seed_keywords):
        raise HTTPException(status_code=400, detail="Укажите offers и seed_keywords")
    # Создать кампанию
    campaign = Campaign(
        user_id=current_user.id,
        name=data.name or "Кампания из офферов",
        language="ru",
        locale="ru-RU",
        region="RU",
        currency="RUB",
        status="active",
        affiliate_rules={"ai": {"auto_rollback_on_cr_drop": True}, "offers": {"auto_switch_on_cr_drop": False}},
    )
    db.add(campaign)
    await db.flush()
    # Добавить офферы
    for o in data.offers[:50]:
        db.add(Offer(
            campaign_id=campaign.id,
            url=(o.url or "").strip(),
            geo=(o.geo or "").strip() or None,
            name=(o.name or "").strip() or None,
            is_active=True,
            priority=0,
        ))
    await db.flush()
    geos = list(dict.fromkeys((o.geo or "RU").strip().upper()[:2] for o in data.offers if (o.geo or "").strip()))
    if not geos:
        geos = ["RU"]
    # Ключи через провайдера
    from app.services.settings_helpers import get_keyword_provider_credentials
    from app.services.dataforseo_service import fetch_keywords_for_keywords as dataforseo_fetch
    from app.services.fetchserp_service import fetch_keywords_for_keywords as fetchserp_fetch

    creds = await get_keyword_provider_credentials(db, current_user.id)
    merged_kw: dict[str, dict] = {}
    if creds:
        provider, c = creds
        fetch_fn = dataforseo_fetch if provider == "dataforseo" else fetchserp_fetch
        limit_per_geo = max(15, data.limit_keywords // len(geos))
        for country in geos[:5]:
            for seed in data.seed_keywords[:3]:
                seed = (seed or "").strip()
                if not seed:
                    continue
                try:
                    if provider == "dataforseo":
                        kws = await fetch_fn(c["login"], c["password"], seed=seed, country=country, limit=limit_per_geo)
                    else:
                        kws, _ = await fetch_fn(c["api_key"], seed=seed, country=country, limit=limit_per_geo)
                    for kw in kws:
                        key_lower = kw["keyword"].lower()
                        if key_lower not in merged_kw or (kw.get("volume") or 0) > (merged_kw[key_lower].get("volume") or 0):
                            merged_kw[key_lower] = {**kw, "region": country}
                except Exception:
                    pass
    result_kw = sorted(merged_kw.values(), key=lambda x: -(x.get("volume") or 0))[:data.limit_keywords]
    for item in result_kw:
        db.add(Keyword(
            campaign_id=campaign.id,
            keyword=item["keyword"].strip(),
            volume=item.get("volume", 0),
            region=item.get("region"),
            source="dataforseo" if creds and creds[0] == "dataforseo" else "fetchserp" if creds else None,
        ))
    await db.flush()
    # Опционально: дорвеи по топу ключей
    created_doorways = 0
    if data.create_doorways and data.domain_id and result_kw:
        dom = (await db.execute(
            select(Domain).where(Domain.id == data.domain_id)
        )).scalar_one_or_none()
        if dom and (dom.campaign_id is None or dom.campaign_id == campaign.id):
            from app.services.generator import generate_doorway
            camp = (await db.execute(select(Campaign).where(Campaign.id == campaign.id))).scalar_one_or_none()
            preferred_layout = (camp.affiliate_rules or {}).get("ai", {}).get("preferred_layout_index") if camp else None
            for i, item in enumerate(result_kw[:20]):
                path = ("/" + (item["keyword"].strip()[:50].replace(" ", "-").replace("/", "-"))).replace("--", "-").rstrip("-") or "/"
                try:
                    gen = await generate_doorway(db, campaign_id=campaign.id, domain_id=dom.id, keyword=item["keyword"], path=path)
                    if gen:
                        dw = Doorway(
                            campaign_id=campaign.id,
                            domain_id=dom.id,
                            path=path,
                            title=gen.get("title"),
                            content=gen.get("content"),
                            meta_description=gen.get("meta_description"),
                            status="draft",
                            layout_index=preferred_layout,
                        )
                        db.add(dw)
                        await db.flush()
                        db.add(DoorwayVersion(doorway_id=dw.id, content_snapshot={"title": dw.title, "content": dw.content, "meta_description": dw.meta_description}))
                        created_doorways += 1
                except Exception:
                    pass
    await db.commit()
    await db.refresh(campaign)
    try:
        from app.api.billing import notify_billing_limits_if_needed
        await notify_billing_limits_if_needed(db, current_user.id)
    except Exception:
        pass
    return {
        "campaign_id": campaign.id,
        "name": campaign.name,
        "offers_added": len(data.offers[:50]),
        "keywords_added": len(result_kw),
        "doorways_created": created_doorways,
    }
