"""Keywords API (semantic module)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, nulls_last

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.keyword import Keyword
from app.models.campaign import Campaign
from app.models.offer import Offer
from app.schemas.keyword import (
    KeywordCreate,
    KeywordBulkCreate,
    KeywordBulkImportFromSuggest,
    KeywordResponse,
    KeywordSuggestFromExternalRequest,
    KeywordSuggestFromExternalResponse,
)

router = APIRouter()


async def _check_campaign(db: AsyncSession, campaign_id: int, user_id: int) -> bool:
    r = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
    )
    return r.scalar_one_or_none() is not None


@router.get("/", response_model=List[KeywordResponse])
async def list_keywords(
    current_user: CurrentUser,
    campaign_id: int,
    db: AsyncSession = Depends(get_db),
):
    ok = await _check_campaign(db, campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    r = await db.execute(
        select(Keyword)
        .where(Keyword.campaign_id == campaign_id)
        .order_by(nulls_last(desc(Keyword.volume)), Keyword.keyword)
    )
    return r.scalars().all()


@router.post("/", response_model=KeywordResponse)
async def create_keyword(
    data: KeywordCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ok = await _check_campaign(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    k = Keyword(**data.model_dump())
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


@router.post("/bulk", response_model=List[KeywordResponse])
async def bulk_create_keywords(
    data: KeywordBulkCreate,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    ok = await _check_campaign(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    created = []
    for kw in data.keywords:
        k = Keyword(
            campaign_id=data.campaign_id,
            keyword=kw.strip(),
            volume=data.volume,
            region=data.region,
            source=data.source,
        )
        db.add(k)
        await db.flush()
        created.append(k)
    await db.commit()
    for k in created:
        await db.refresh(k)
    return created


@router.post("/suggest-from-external", response_model=KeywordSuggestFromExternalResponse)
async def suggest_keywords_from_external(
    data: KeywordSuggestFromExternalRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Fetch keyword suggestions from DataForSeo by seed + country."""
    ok = await _check_campaign(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    from app.services.settings_helpers import get_user_dataforseo_credentials
    from app.services.dataforseo_service import fetch_keywords_for_keywords

    creds = await get_user_dataforseo_credentials(db, current_user.id)
    if not creds:
        raise HTTPException(
            status_code=400,
            detail="Укажите DataForSeo логин и пароль в Настройках → Интеграции",
        )
    login, password = creds
    keywords = await fetch_keywords_for_keywords(
        login, password,
        seed=data.seed,
        country=data.country,
        limit=data.limit,
    )
    return KeywordSuggestFromExternalResponse(keywords=keywords, source="dataforseo")


@router.post("/suggest-by-offers-geo-batch", response_model=KeywordSuggestFromExternalResponse)
async def suggest_keywords_by_offers_geo(
    data: KeywordSuggestFromExternalRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Fetch keywords for each geo from campaign offers, merge and deduplicate by volume."""
    ok = await _check_campaign(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    r = await db.execute(
        select(Offer.geo).where(
            Offer.campaign_id == data.campaign_id,
            Offer.geo.isnot(None),
            Offer.geo != "",
        ).distinct()
    )
    geos = list(dict.fromkeys(row[0] for row in r.all() if row[0]))
    if not geos:
        raise HTTPException(status_code=400, detail="У кампании нет офферов с указанным geo. Добавьте офферы с полем geo.")
    from app.services.settings_helpers import get_user_dataforseo_credentials
    from app.services.dataforseo_service import fetch_keywords_for_keywords

    creds = await get_user_dataforseo_credentials(db, current_user.id)
    if not creds:
        raise HTTPException(status_code=400, detail="Укажите DataForSeo в Настройках → Интеграции")
    login, password = creds
    merged: dict[str, dict] = {}
    limit_per_geo = max(20, data.limit // len(geos))
    for country in geos[:5]:
        kws = await fetch_keywords_for_keywords(
            login, password, seed=data.seed, country=country, limit=limit_per_geo
        )
        for kw in kws:
            key_lower = kw["keyword"].lower()
            if key_lower not in merged or (kw.get("volume", 0) or 0) > (merged[key_lower].get("volume") or 0):
                merged[key_lower] = {**kw, "region": country}
    result = sorted(merged.values(), key=lambda x: -(x.get("volume") or 0))[:data.limit]
    out = [{"keyword": x["keyword"], "volume": x.get("volume", 0), "cpc": x.get("cpc", 0)} for x in result]
    return KeywordSuggestFromExternalResponse(keywords=out, source="dataforseo")


@router.get("/suggest-by-offers-geo")
async def get_unique_geo_from_offers(
    campaign_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Return unique geo codes from campaign offers for keyword suggestion."""
    ok = await _check_campaign(db, campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    r = await db.execute(
        select(Offer.geo).where(
            Offer.campaign_id == campaign_id,
            Offer.geo.isnot(None),
            Offer.geo != "",
        ).distinct()
    )
    geos = [row[0] for row in r.all() if row[0]]
    return {"geos": list(dict.fromkeys(geos))}


@router.post("/bulk-import-from-suggest", response_model=List[KeywordResponse])
async def bulk_import_from_suggest(
    data: KeywordBulkImportFromSuggest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Import suggested keywords (with volume) into campaign. Skips duplicates."""
    ok = await _check_campaign(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    existing_r = await db.execute(select(Keyword.keyword).where(Keyword.campaign_id == data.campaign_id))
    existing_lower = {row[0].lower() for row in existing_r.all() if row[0]}
    created = []
    for item in data.items:
        if item.keyword.strip().lower() in existing_lower:
            continue
        k = Keyword(
            campaign_id=data.campaign_id,
            keyword=item.keyword.strip(),
            volume=item.volume,
            region=data.region,
            source="dataforseo",
        )
        db.add(k)
        await db.flush()
        created.append(k)
        existing_lower.add(item.keyword.strip().lower())
    await db.commit()
    for k in created:
        await db.refresh(k)
    return created


@router.delete("/{keyword_id}", status_code=204)
async def delete_keyword(
    keyword_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Keyword).join(Campaign).where(
            Keyword.id == keyword_id, Campaign.user_id == current_user.id
        )
    )
    k = r.scalar_one_or_none()
    if not k:
        raise HTTPException(status_code=404, detail="Keyword not found")
    await db.delete(k)
    await db.commit()
    return None
