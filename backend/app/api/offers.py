"""Offers API - geo/device routing."""

import csv
import io
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.offer import Offer
from app.models.campaign import Campaign
from app.schemas.offer import OfferCreate, OfferUpdate, OfferResponse

router = APIRouter()


def _parse_zeydoo_csv(content: bytes, offer_url: str, campaign_id: int) -> list[dict]:
    """Parse Zeydoo export CSV. Columns: Offer ID, Offer name, Conversion type, Geo, eCPM, PO, Platform, OS."""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    rows = []
    seen = set()
    for row in reader:
        # Normalize keys (strip quotes/spaces from header)
        row = {k.strip().strip('"'): v for k, v in row.items()}
        name = (row.get("Offer name") or "").strip() or None
        geo_raw = (row.get("Geo") or "").strip()
        geo = geo_raw.lower() if geo_raw else None
        po = (row.get("PO") or "").strip().replace("$", "").strip()
        rate = po if po else None
        platform = (row.get("Platform") or "").strip().lower()
        device = "mobile" if platform == "mobile" else ("desktop" if platform == "desktop" else None)
        if not offer_url.strip():
            continue
        # One offer per geo row; skip duplicates (same geo+device)
        key = (geo or "", device or "")
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "campaign_id": campaign_id,
            "url": offer_url.strip(),
            "name": name,
            "rate": rate,
            "amount": None,
            "term": None,
            "geo": geo,
            "device": device,
            "priority": 0,
            "is_active": True,
        })
    return rows


async def _check(db: AsyncSession, campaign_id: int, user_id: int) -> bool:
    r = await db.execute(
        select(Campaign).where(Campaign.id == campaign_id, Campaign.user_id == user_id)
    )
    return r.scalar_one_or_none() is not None


@router.get("/", response_model=List[OfferResponse])
async def list_offers(current_user: CurrentUser, campaign_id: int, db: AsyncSession = Depends(get_db)):
    if not await _check(db, campaign_id, current_user.id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    r = await db.execute(select(Offer).where(Offer.campaign_id == campaign_id).order_by(Offer.priority.desc()))
    return list(r.scalars().all())


@router.post("/", response_model=OfferResponse)
async def create_offer(data: OfferCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    if not await _check(db, data.campaign_id, current_user.id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    o = Offer(**data.model_dump())
    db.add(o)
    await db.commit()
    await db.refresh(o)
    return o


@router.patch("/{offer_id}", response_model=OfferResponse)
async def update_offer(offer_id: int, data: OfferUpdate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Offer).join(Campaign).where(Offer.id == offer_id, Campaign.user_id == current_user.id))
    o = r.scalar_one_or_none()
    if not o:
        raise HTTPException(status_code=404, detail="Offer not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(o, k, v)
    await db.commit()
    await db.refresh(o)
    return o


@router.delete("/{offer_id}", status_code=204)
async def delete_offer(offer_id: int, current_user: CurrentUser, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(Offer).join(Campaign).where(Offer.id == offer_id, Campaign.user_id == current_user.id))
    o = r.scalar_one_or_none()
    if not o:
        raise HTTPException(status_code=404, detail="Offer not found")
    await db.delete(o)
    await db.commit()
    return None


@router.post("/import")
async def import_zeydoo_csv(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    campaign_id: int = Form(...),
    offer_url: str = Form(..., description="Трекинг-ссылка оффера из Zeydoo (одна на все гео)"),
    file: UploadFile = File(..., description="CSV из Zeydoo (Export to CSV со страницы оффера)"),
):
    """Импорт офферов из выгрузки Zeydoo (Export to CSV). По каждой строке (гео) создаётся оффер с указанным URL."""
    if not await _check(db, campaign_id, current_user.id):
        raise HTTPException(status_code=404, detail="Campaign not found")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Нужен файл .csv")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Файл пустой")
    try:
        rows = _parse_zeydoo_csv(content, offer_url, campaign_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка разбора CSV: {e}")
    if not rows:
        raise HTTPException(status_code=400, detail="В CSV нет подходящих строк или не указан URL оффера")
    for r in rows:
        db.add(Offer(**r))
    await db.commit()
    return {"imported": len(rows)}
