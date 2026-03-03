"""Doorways API."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.doorway import Doorway, DoorwayVersion, DoorwayMetrics
from app.models.campaign import Campaign
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
            generate_faq=data.generate_faq,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    doorway_id = None
    if data.save and result:
        cloaking = {}
        if result.get("faq_qa"):
            cloaking["faq_qa"] = result["faq_qa"]
        camp = (await db.execute(select(Campaign).where(Campaign.id == data.campaign_id))).scalar_one_or_none()
        preferred_layout = None
        if camp and camp.affiliate_rules and isinstance(camp.affiliate_rules.get("ai"), dict):
            preferred_layout = camp.affiliate_rules["ai"].get("preferred_layout_index")
        dw = Doorway(
            campaign_id=data.campaign_id,
            domain_id=data.domain_id,
            path=data.path,
            title=result.get("title"),
            content=result.get("content"),
            meta_description=result.get("meta_description"),
            status="draft",
            cloaking_rules=cloaking if cloaking else None,
            layout_index=preferred_layout if preferred_layout is not None else None,
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
        try:
            from app.api.billing import notify_billing_limits_if_needed
            await notify_billing_limits_if_needed(db, current_user.id)
        except Exception:
            pass
    return DoorwayGenerateResponse(
        title=result.get("title", ""),
        meta_description=result.get("meta_description", ""),
        content=result.get("content", ""),
        html=result.get("html", ""),
        doorway_id=doorway_id,
        validation_violations=result.get("validation_violations"),
        faq_qa=result.get("faq_qa"),
    )


@router.post("/generate-batch", response_model=DoorwayBatchGenerateResponse)
async def generate_batch(
    data: DoorwayBatchGenerateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if not (data.items and len(data.items) > 0):
        raise HTTPException(status_code=400, detail="Добавьте ключи в поле пакетной генерации (по одному на строку).")
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
                generate_faq=data.generate_faq,
            )
        except (ValueError, Exception) as e:
            results.append({"keyword": item.keyword, "status": "error", "error": str(e)[:200]})
            continue
        doorway_id = None
        try:
            cloaking = {}
            if gen_result.get("faq_qa"):
                cloaking["faq_qa"] = gen_result["faq_qa"]
            camp = (await db.execute(select(Campaign).where(Campaign.id == item.campaign_id))).scalar_one_or_none()
            preferred_layout = None
            if camp and camp.affiliate_rules and isinstance(camp.affiliate_rules.get("ai"), dict):
                preferred_layout = camp.affiliate_rules["ai"].get("preferred_layout_index")
            dw = Doorway(
                campaign_id=item.campaign_id,
                domain_id=item.domain_id,
                path=item.path,
                title=gen_result.get("title"),
                content=gen_result.get("content"),
                meta_description=gen_result.get("meta_description"),
                status="draft",
                cloaking_rules=cloaking if cloaking else None,
                layout_index=preferred_layout if preferred_layout is not None else None,
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
    if created > 0:
        try:
            from app.api.billing import notify_billing_limits_if_needed
            await notify_billing_limits_if_needed(db, current_user.id)
        except Exception:
            pass
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
    camp = (await db.execute(select(Campaign).where(Campaign.id == data.campaign_id))).scalar_one_or_none()
    preferred_layout = None
    if camp and camp.affiliate_rules and isinstance(camp.affiliate_rules.get("ai"), dict):
        preferred_layout = camp.affiliate_rules["ai"].get("preferred_layout_index")
    dump = data.model_dump()
    if preferred_layout is not None:
        dump["layout_index"] = preferred_layout
    doorway = Doorway(**dump)
    db.add(doorway)
    await db.commit()
    await db.refresh(doorway)
    try:
        from app.api.billing import notify_billing_limits_if_needed
        await notify_billing_limits_if_needed(db, current_user.id)
    except Exception:
        pass
    return doorway


@router.get("/{doorway_id}/quality-check")
async def doorway_quality_check(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Pre-deploy content quality check (anti-detection) + campaign readiness."""
    from app.services.anti_detection import check_content_quality

    result = await db.execute(
        select(Doorway, Campaign)
        .join(Campaign)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Doorway not found")
    doorway, campaign = row
    keyword = None
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
    errors = list(r.errors)
    warnings = list(r.warnings)
    if not (campaign.affiliate_url or "").strip():
        errors.append("Кампания без affiliate URL — CTA не будет работать")
    cr = doorway.cloaking_rules or {}
    camp_settings = (campaign.affiliate_rules or {}).get("settings") or {}
    if not (cr.get("urgency_block") or camp_settings.get("urgency_block")) and not cr.get("social_proof"):
        warnings.append("Нет urgency или social proof — можно добавить в Конверсию")
    if not cr.get("faq_qa"):
        warnings.append("Нет FAQ — можно сгенерировать при создании дорвея")
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings}


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


class ApplyVariantRequest(BaseModel):
    variant_index: int = 0


@router.post("/{doorway_id}/add-variant")
async def doorway_add_variant(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate new content variant with AI and add to content_variants."""
    from app.services.generator import generate_doorway
    from app.services.settings_helpers import get_user_openai_key

    r = await db.execute(
        select(Doorway, Campaign)
        .join(Campaign)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    row = r.first()
    if not row:
        raise HTTPException(404, "Doorway not found")
    dw, camp = row
    keyword = (dw.title or "").split()[:3]
    keyword = " ".join(keyword) if keyword else "займ"
    try:
        result = await generate_doorway(
            db,
            campaign_id=dw.campaign_id,
            domain_id=dw.domain_id,
            keyword=keyword,
            path=dw.path or "/",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    variant = {
        "title": result.get("title"),
        "content": result.get("content"),
        "meta_description": result.get("meta_description"),
        "cta_text": "Оформить заявку",
    }
    variants = list(dw.content_variants or [])
    variants.append(variant)
    dw.content_variants = variants
    await db.commit()
    return {"status": "ok", "variant_index": len(variants) - 1}


@router.post("/{doorway_id}/apply-variant")
async def doorway_apply_variant(
    doorway_id: int,
    data: ApplyVariantRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Make variant at index primary (swap with current content)."""
    r = await db.execute(
        select(Doorway)
        .join(Campaign)
        .where(Doorway.id == doorway_id, Campaign.user_id == current_user.id)
    )
    dw = r.scalar_one_or_none()
    if not dw:
        raise HTTPException(404, "Doorway not found")
    variants = list(dw.content_variants or [])
    if data.variant_index < 0 or data.variant_index >= len(variants):
        raise HTTPException(400, "Invalid variant_index")
    v = variants[data.variant_index]
    snap = {"title": dw.title, "content": dw.content, "meta_description": dw.meta_description}
    db.add(DoorwayVersion(doorway_id=dw.id, content_snapshot=snap))
    dw.title = v.get("title", dw.title)
    dw.content = v.get("content", dw.content)
    dw.meta_description = v.get("meta_description", dw.meta_description)
    if v.get("cta_text"):
        cr = dict(dw.cloaking_rules or {})
        cr["cta_by_device"] = {"desktop": v["cta_text"], "mobile": v.get("cta_mobile") or v["cta_text"]}
        dw.cloaking_rules = cr
    await db.commit()
    return {"status": "ok", "message": f"Variant {data.variant_index} applied"}


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
    from app.models.doorway_source_metrics import DoorwaySourceMetrics
    from app.models.ab_variant import DoorwayABVariant
    await db.execute(delete(DoorwayVersion).where(DoorwayVersion.doorway_id == doorway_id))
    await db.execute(delete(DoorwayMetrics).where(DoorwayMetrics.doorway_id == doorway_id))
    await db.execute(delete(DoorwaySourceMetrics).where(DoorwaySourceMetrics.doorway_id == doorway_id))
    await db.execute(delete(DoorwayABVariant).where(DoorwayABVariant.doorway_id == doorway_id))
    await db.delete(doorway)
    await db.commit()
    return None


class BatchDeleteRequest(BaseModel):
    doorway_ids: List[int]


@router.post("/batch-delete")
async def batch_delete_doorways(
    data: BatchDeleteRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    if not data.doorway_ids:
        return {"deleted": 0, "message": "Нет выбранных дорвеев"}
    # Только дорвеи текущего пользователя (через кампанию)
    result = await db.execute(
        select(Doorway.id)
        .join(Campaign)
        .where(Doorway.id.in_(data.doorway_ids), Campaign.user_id == current_user.id)
    )
    ids = [row[0] for row in result.all()]
    if not ids:
        return {"deleted": 0, "message": "Нет доступных дорвеев для удаления"}
    # Сначала удаляем связанные записи (FK без CASCADE)
    from app.models.doorway_source_metrics import DoorwaySourceMetrics
    from app.models.ab_variant import DoorwayABVariant
    await db.execute(delete(DoorwayVersion).where(DoorwayVersion.doorway_id.in_(ids)))
    await db.execute(delete(DoorwayMetrics).where(DoorwayMetrics.doorway_id.in_(ids)))
    await db.execute(delete(DoorwaySourceMetrics).where(DoorwaySourceMetrics.doorway_id.in_(ids)))
    await db.execute(delete(DoorwayABVariant).where(DoorwayABVariant.doorway_id.in_(ids)))
    await db.execute(delete(Doorway).where(Doorway.id.in_(ids)))
    await db.commit()
    return {"deleted": len(ids), "message": f"Удалено дорвеев: {len(ids)}"}


class BatchQualityCheckRequest(BaseModel):
    doorway_ids: List[int]


@router.post("/batch-quality-check")
async def batch_quality_check(
    data: BatchQualityCheckRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Пакетная проверка качества выбранных дорвеев (то же, что Quality по одному)."""
    if not data.doorway_ids:
        return {"results": []}
    from app.models.keyword import Keyword
    from app.services.anti_detection import check_content_quality

    result = await db.execute(
        select(Doorway, Campaign)
        .join(Campaign)
        .where(Doorway.id.in_(data.doorway_ids), Campaign.user_id == current_user.id)
    )
    rows = result.all()
    kw_r = await db.execute(
        select(Keyword.campaign_id, Keyword.keyword).where(
            Keyword.campaign_id.in_(list({r[1].id for r in rows}))
        )
    )
    kw_by_camp = {}
    for camp_id, kw in kw_r.all():
        if camp_id not in kw_by_camp:
            kw_by_camp[camp_id] = kw
    out = []
    for doorway, campaign in rows:
        keyword = kw_by_camp.get(doorway.campaign_id)
        r = check_content_quality(
            title=doorway.title or "",
            meta_description=doorway.meta_description or "",
            content=doorway.content or "",
            keyword=keyword,
        )
        errors = list(r.errors)
        warnings = list(r.warnings)
        if not (campaign.affiliate_url or "").strip():
            errors.append("Кампания без affiliate URL — CTA не будет работать")
        cr = doorway.cloaking_rules or {}
        camp_settings = (campaign.affiliate_rules or {}).get("settings") or {}
        if not (cr.get("urgency_block") or camp_settings.get("urgency_block")) and not cr.get("social_proof"):
            warnings.append("Нет urgency или social proof — можно добавить в Конверсию")
        if not cr.get("faq_qa"):
            warnings.append("Нет FAQ — можно сгенерировать при создании дорвея")
        out.append({
            "doorway_id": doorway.id,
            "path": doorway.path,
            "title": (doorway.title or "")[:60],
            "ok": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        })
    return {"results": out}
