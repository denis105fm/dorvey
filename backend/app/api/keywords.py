"""Keywords API (semantic module)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
    """Fetch keyword suggestions from selected provider (DataForSeo or FetchSERP) by seed + country."""
    ok = await _check_campaign(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    from app.services.settings_helpers import get_keyword_provider_credentials
    from app.services.dataforseo_service import fetch_keywords_for_keywords as dataforseo_fetch
    from app.services.fetchserp_service import fetch_keywords_for_keywords as fetchserp_fetch

    creds = await get_keyword_provider_credentials(db, current_user.id)
    if not creds:
        raise HTTPException(
            status_code=400,
            detail="Выберите провайдера подсказки ключей в Настройках → Интеграции и укажите данные для API (DataForSeo: логин и пароль, FetchSERP: API ключ).",
        )
    provider, c = creds
    if provider == "dataforseo":
        keywords = await dataforseo_fetch(
            c["login"], c["password"],
            seed=data.seed,
            country=data.country,
            limit=data.limit,
        )
    elif provider == "fetchserp":
        keywords, _ = await fetchserp_fetch(
            c["api_key"],
            seed=data.seed,
            country=data.country,
            limit=data.limit,
        )
    else:
        raise HTTPException(status_code=400, detail=f"Провайдер «{provider}» не поддерживается.")
    return KeywordSuggestFromExternalResponse(keywords=keywords, source=provider)


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
    from app.services.settings_helpers import get_keyword_provider_credentials
    from app.services.dataforseo_service import fetch_keywords_for_keywords as dataforseo_fetch
    from app.services.fetchserp_service import fetch_keywords_for_keywords as fetchserp_fetch

    creds = await get_keyword_provider_credentials(db, current_user.id)
    if not creds:
        raise HTTPException(status_code=400, detail="Выберите провайдера подсказки ключей в Настройках и укажите данные для API.")
    provider, c = creds
    fetch_fn = dataforseo_fetch if provider == "dataforseo" else fetchserp_fetch
    if provider == "dataforseo":
        auth = (c["login"], c["password"])
    else:
        auth = c["api_key"]
    merged: dict[str, dict] = {}
    limit_per_geo = max(20, data.limit // len(geos))
    for country in geos[:5]:
        if provider == "dataforseo":
            kws = await fetch_fn(auth[0], auth[1], seed=data.seed, country=country, limit=limit_per_geo)
        else:
            kws, _ = await fetch_fn(auth, seed=data.seed, country=country, limit=limit_per_geo)
        for kw in kws:
            key_lower = kw["keyword"].lower()
            if key_lower not in merged or (kw.get("volume", 0) or 0) > (merged[key_lower].get("volume") or 0):
                merged[key_lower] = {**kw, "region": country}
    result = sorted(merged.values(), key=lambda x: -(x.get("volume") or 0))[:data.limit]
    out = [{"keyword": x["keyword"], "volume": x.get("volume", 0), "cpc": x.get("cpc", 0)} for x in result]
    return KeywordSuggestFromExternalResponse(keywords=out, source=provider)


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
        source_val = (data.source or "dataforseo").strip() or "dataforseo"
        k = Keyword(
            campaign_id=data.campaign_id,
            keyword=item.keyword.strip(),
            volume=item.volume,
            region=data.region,
            source=source_val,
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


# --- Стартовый набор ниш и авто-подсказки ---

@router.get("/startup-niches")
async def get_startup_niches(current_user: CurrentUser):
    """Справочник ниш для стартового набора ключей (seed-фразы для провайдера)."""
    from app.services.startup_niches import STARTUP_NICHES
    return {"niches": [{"id": n["id"], "name": n["name"], "seeds": n["seeds"]} for n in STARTUP_NICHES]}


class StartupKeywordsRequest(BaseModel):
    seeds: List[str]  # ниши/фразы для запроса к провайдеру
    country: str = "RU"
    limit_per_seed: int = 30
    campaign_id: int | None = None
    auto_import: bool = False


@router.post("/startup-keywords")
async def fetch_startup_keywords(
    data: StartupKeywordsRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Запрос к провайдеру по списку ниш/фраз → топ ключей по объёму.
    Если auto_import=True и campaign_id задан — импорт в кампанию.
    """
    from app.services.settings_helpers import get_keyword_provider_credentials
    from app.services.dataforseo_service import fetch_keywords_for_keywords as dataforseo_fetch
    from app.services.fetchserp_service import fetch_keywords_for_keywords as fetchserp_fetch

    creds = await get_keyword_provider_credentials(db, current_user.id)
    if not creds:
        raise HTTPException(
            status_code=400,
            detail="Выберите провайдера подсказки ключей в Настройках и укажите API данные.",
        )
    provider, c = creds
    fetch_fn = dataforseo_fetch if provider == "dataforseo" else fetchserp_fetch
    if provider == "dataforseo":
        auth = (c["login"], c["password"])
    else:
        auth = c["api_key"]

    merged: dict[str, dict] = {}
    for seed in (data.seeds or [])[:10]:
        seed = (seed or "").strip()
        if not seed:
            continue
        if provider == "dataforseo":
            kws = await fetch_fn(auth[0], auth[1], seed=seed, country=data.country, limit=data.limit_per_seed)
        else:
            kws, _ = await fetch_fn(auth, seed=seed, country=data.country, limit=data.limit_per_seed)
        for kw in kws:
            key_lower = kw["keyword"].lower()
            if key_lower not in merged or (kw.get("volume") or 0) > (merged[key_lower].get("volume") or 0):
                merged[key_lower] = kw
    result = sorted(merged.values(), key=lambda x: -(x.get("volume") or 0))
    keywords = [{"keyword": x["keyword"], "volume": x.get("volume", 0), "cpc": x.get("cpc", 0)} for x in result]

    imported = 0
    if data.auto_import and data.campaign_id and keywords:
        ok = await _check_campaign(db, data.campaign_id, current_user.id)
        if ok:
            existing_r = await db.execute(select(Keyword.keyword).where(Keyword.campaign_id == data.campaign_id))
            existing_lower = {row[0].lower() for row in existing_r.all() if row[0]}
            for item in keywords[:200]:
                if item["keyword"].strip().lower() in existing_lower:
                    continue
                k = Keyword(
                    campaign_id=data.campaign_id,
                    keyword=item["keyword"].strip(),
                    volume=item.get("volume", 0),
                    region=data.country,
                    source=provider,
                )
                db.add(k)
                await db.flush()
                imported += 1
                existing_lower.add(item["keyword"].strip().lower())
            await db.commit()

    return {"keywords": keywords, "source": provider, "imported": imported}


class AutoPullImportRequest(BaseModel):
    campaign_id: int
    seed: str
    country: str = "RU"
    limit: int = 50


@router.post("/auto-pull-and-import")
async def auto_pull_and_import(
    data: AutoPullImportRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Полная автоматизация подсказок: подтянуть ключи из выбранного провайдера и сразу импортировать в кампанию (без ручного выбора).
    """
    ok = await _check_campaign(db, data.campaign_id, current_user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Campaign not found")
    from app.services.settings_helpers import get_keyword_provider_credentials
    from app.services.dataforseo_service import fetch_keywords_for_keywords as dataforseo_fetch
    from app.services.fetchserp_service import fetch_keywords_for_keywords as fetchserp_fetch

    creds = await get_keyword_provider_credentials(db, current_user.id)
    if not creds:
        raise HTTPException(status_code=400, detail="Настройте провайдера подсказки ключей в Настройках.")
    provider, c = creds
    if provider == "dataforseo":
        keywords = await dataforseo_fetch(
            c["login"], c["password"],
            seed=data.seed, country=data.country, limit=data.limit,
        )
        fetchserp_debug = None
    else:
        keywords, fetchserp_debug = await fetchserp_fetch(c["api_key"], seed=data.seed, country=data.country, limit=data.limit)

    existing_r = await db.execute(select(Keyword.keyword).where(Keyword.campaign_id == data.campaign_id))
    existing_lower = {row[0].lower() for row in existing_r.all() if row[0]}
    created = []
    for item in keywords:
        if item["keyword"].strip().lower() in existing_lower:
            continue
        k = Keyword(
            campaign_id=data.campaign_id,
            keyword=item["keyword"].strip(),
            volume=item.get("volume", 0),
            region=data.country,
            source=provider,
        )
        db.add(k)
        await db.flush()
        created.append(k)
        existing_lower.add(item["keyword"].strip().lower())
    await db.commit()
    for k in created:
        await db.refresh(k)
    result = {"imported": len(created), "source": provider, "keywords": [{"keyword": k.keyword, "volume": k.volume} for k in created]}
    if len(created) == 0 and not keywords:
        result["hint"] = "Провайдер вернул 0 ключей. Проверьте Настройки → Интеграции (API ключ FetchSERP), попробуйте одну чёткую seed-фразу на английском, например: casual clicker game"
        if provider == "fetchserp" and fetchserp_debug:
            result["debug"] = fetchserp_debug
    elif len(created) == 0 and keywords:
        result["hint"] = "Все подтянутые ключи уже есть в кампании."
    return result
