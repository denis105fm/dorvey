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
from app.models.domain import Domain
from app.models.server import Server
from app.services.deploy import remove_doorway_from_server
from app.schemas.doorway import (
    DoorwayCreate,
    DoorwayUpdate,
    DoorwayResponse,
    DoorwayGenerateRequest,
    DoorwayGenerateResponse,
    DoorwayBatchGenerateRequest,
    DoorwayBatchGenerateResponse,
)
from app.services.generator import generate_doorway, _keyword_to_slug
from app.services.dataforseo_service import get_language_code

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

    geos: list[str | None] = []
    if data.target_geos and len(data.target_geos) > 1:
        geos = [g.strip().upper()[:2] for g in data.target_geos if (g or "").strip()]
    elif data.target_geos and len(data.target_geos) == 1 and (data.target_geos[0] or "").strip():
        geos = [(data.target_geos[0] or "").strip().upper()[:2]]
    elif data.target_geo and (data.target_geo or "").strip():
        geos = [(data.target_geo or "").strip().upper()[:2]]
    if not geos:
        geos = [None]

    base_path = (data.path or "/").strip() or "/"
    slug = _keyword_to_slug(data.keyword) if base_path == "/" else base_path.strip("/").split("/")[0] or _keyword_to_slug(data.keyword)
    created_ids: list[int] = []
    last_result = None

    for geo in geos:
        if len(geos) > 1 and geo:
            path_use = f"/{get_language_code(geo)}/{slug}"
        else:
            path_use = base_path if base_path != "/" else f"/{slug}"
        try:
            result = await generate_doorway(
                db,
                campaign_id=data.campaign_id,
                domain_id=data.domain_id,
                keyword=data.keyword,
                path=path_use,
                generate_faq=data.generate_faq,
                generate_quiz=data.generate_quiz,
                target_geo=geo,
            )
        except ValueError as e:
            if not created_ids:
                raise HTTPException(status_code=404, detail=str(e))
            break
        last_result = result
        if data.save and result:
            cloaking = {}
            if result.get("faq_qa"):
                cloaking["faq_qa"] = result["faq_qa"]
            if result.get("quiz_questions"):
                cloaking["quiz"] = {"enabled": True, "questions": result["quiz_questions"]}
            camp = (await db.execute(select(Campaign).where(Campaign.id == data.campaign_id))).scalar_one_or_none()
            preferred_layout = None
            if camp and camp.affiliate_rules and isinstance(camp.affiliate_rules.get("ai"), dict):
                preferred_layout = camp.affiliate_rules["ai"].get("preferred_layout_index")
            dw = Doorway(
                campaign_id=data.campaign_id,
                domain_id=data.domain_id,
                path=path_use,
                title=result.get("title"),
                content=result.get("content"),
                meta_description=result.get("meta_description"),
                status="draft",
                cloaking_rules=cloaking if cloaking else None,
                layout_index=preferred_layout if preferred_layout is not None else None,
                target_geo=geo,
            )
            db.add(dw)
            await db.commit()
            await db.refresh(dw)
            created_ids.append(dw.id)
            if len(created_ids) == 1:
                snap = {"title": dw.title, "content": dw.content, "meta_description": dw.meta_description}
                ver = DoorwayVersion(doorway_id=dw.id, content_snapshot=snap)
                db.add(ver)
                await db.commit()
            else:
                snap = {"title": dw.title, "content": dw.content, "meta_description": dw.meta_description}
                db.add(DoorwayVersion(doorway_id=dw.id, content_snapshot=snap))
                await db.commit()
        if len(created_ids) == 1:
            try:
                from app.api.billing import notify_billing_limits_if_needed
                await notify_billing_limits_if_needed(db, current_user.id)
            except Exception:
                pass

    if not last_result:
        raise HTTPException(status_code=404, detail="Campaign or domain not found")
    return DoorwayGenerateResponse(
        title=last_result.get("title", ""),
        meta_description=last_result.get("meta_description", ""),
        content=last_result.get("content", ""),
        html=last_result.get("html", ""),
        doorway_id=created_ids[0] if created_ids else None,
        created_count=len(created_ids),
        validation_violations=last_result.get("validation_violations"),
        faq_qa=last_result.get("faq_qa"),
    )


@router.post("/generate-batch")
async def generate_batch(
    data: DoorwayBatchGenerateRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Start batch generation in background. Returns task_id to poll status at GET /generate-batch/{task_id}/status."""
    if not (data.items and len(data.items) > 0):
        raise HTTPException(status_code=400, detail="Добавьте ключи в поле пакетной генерации (по одному на строку).")
    from app.tasks.doorway_tasks import generate_batch_async
    from app.services.generate_batch_state import set_state

    items_payload = [
        {
            "campaign_id": it.campaign_id,
            "domain_id": it.domain_id,
            "keyword": it.keyword,
            "path": it.path or "/",
            "target_geo": it.target_geo,
            "target_geos": it.target_geos,
        }
        for it in data.items[:50]
    ]
    task = generate_batch_async.delay(
        user_id=current_user.id,
        items=items_payload,
        generate_faq=data.generate_faq,
        generate_quiz=data.generate_quiz,
        target_geos=data.target_geos,
    )
    set_state(task.id, {"user_id": current_user.id})
    return {"status": "queued", "task_id": task.id}


@router.get("/generate-batch/{task_id}/status")
async def generate_batch_status(
    task_id: str,
    current_user: CurrentUser,
):
    """Get batch generation progress (list, progress bar)."""
    import asyncio
    from app.services.generate_batch_state import get_state
    state = await asyncio.to_thread(get_state, task_id)
    if not state or state.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task_id,
        "status": state.get("status", "running"),
        "total": state.get("total", 0),
        "current_index": state.get("current_index", 0),
        "created": state.get("created", 0),
        "error": state.get("error"),
        "results": state.get("results") or [],
    }


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
    from app.services.anti_detection import check_content_quality, CODE_NO_URGENCY_SOCIAL_PROOF, CODE_NO_FAQ

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
    warning_codes = list(r.warning_codes)
    if not (campaign.affiliate_url or "").strip():
        errors.append("Кампания без affiliate URL — CTA не будет работать")
    cr = doorway.cloaking_rules or {}
    camp_settings = (campaign.affiliate_rules or {}).get("settings") or {}
    if not (cr.get("urgency_block") or camp_settings.get("urgency_block")) and not cr.get("social_proof"):
        warnings.append("Нет urgency или social proof — можно добавить в Конверсию")
        warning_codes.append((CODE_NO_URGENCY_SOCIAL_PROOF, "Нет urgency или social proof — можно добавить в Конверсию"))
    if not cr.get("faq_qa"):
        warnings.append("Нет FAQ — можно сгенерировать при создании дорвея")
        warning_codes.append((CODE_NO_FAQ, "Нет FAQ — можно сгенерировать при создании дорвея"))
    return {"ok": len(errors) == 0, "errors": errors, "warnings": warnings, "warning_codes": [{"code": c, "message": m} for c, m in warning_codes]}


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
    payload = data.model_dump(exclude_unset=True)
    quiz_enabled = payload.pop("quiz_enabled", None)
    if quiz_enabled is not None:
        cr = dict(doorway.cloaking_rules or {})
        quiz = dict(cr.get("quiz") or {})
        quiz["enabled"] = quiz_enabled
        cr["quiz"] = quiz
        doorway.cloaking_rules = cr
    for k, v in payload.items():
        setattr(doorway, k, v)
    await db.commit()
    await db.refresh(doorway)
    # При постановке на паузу снимаем страницу с сервера
    if payload.get("status") == "paused":
        srv_r = await db.execute(
            select(Server)
            .join(Domain, Domain.server_id == Server.id)
            .where(Domain.id == doorway.domain_id)
        )
        srv_row = srv_r.first()
        if srv_row:
            srv = srv_row[0]
            remove_doorway_from_server(
                server=srv,
                path=doorway.path or "/",
                base_path=srv.path or "/var/www/html",
            )
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


@router.post("/{doorway_id}/generate-quiz")
async def doorway_generate_quiz(
    doorway_id: int,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate quiz for an existing doorway (topic from title/path, theme from offer/campaign)."""
    from app.services.generator import generate_quiz_for_doorway
    quiz_questions, err = await generate_quiz_for_doorway(db, doorway_id, current_user.id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return {"quiz_questions": quiz_questions, "message": "Квиз добавлен"}


class BatchGenerateQuizRequest(BaseModel):
    doorway_ids: List[int]


@router.post("/batch-generate-quiz")
async def batch_generate_quiz(
    data: BatchGenerateQuizRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate quiz for multiple existing doorways. Returns per-doorway results."""
    from app.services.generator import generate_quiz_for_doorway
    if not data.doorway_ids:
        return {"results": [], "message": "Нет дорвеев"}
    results = []
    for dw_id in data.doorway_ids:
        quiz_questions, err = await generate_quiz_for_doorway(db, dw_id, current_user.id)
        results.append({
            "doorway_id": dw_id,
            "ok": err is None,
            "quiz_questions": quiz_questions if not err else None,
            "error": err,
        })
    return {"results": results}


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

    # Удаляем файлы с сервера до удаления записи
    srv_r = await db.execute(
        select(Server)
        .join(Domain, Domain.server_id == Server.id)
        .where(Domain.id == doorway.domain_id)
    )
    srv_row = srv_r.first()
    if srv_row:
        srv = srv_row[0]
        ok, _ = remove_doorway_from_server(
            server=srv,
            path=doorway.path or "/",
            base_path=srv.path or "/var/www/html",
        )
        # не падаем при ошибке удаления с сервера (файла могло не быть)

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
    """Start batch delete in background. Returns task_id to poll status at GET /doorways/batch-delete/{task_id}/status."""
    if not data.doorway_ids:
        return {"deleted": 0, "message": "Нет выбранных дорвеев"}
    result = await db.execute(
        select(Doorway.id)
        .join(Campaign)
        .where(Doorway.id.in_(data.doorway_ids), Campaign.user_id == current_user.id)
    )
    ids = [row[0] for row in result.all()]
    if not ids:
        return {"deleted": 0, "message": "Нет доступных дорвеев для удаления"}
    from app.tasks.doorway_tasks import delete_batch_async
    from app.services.delete_batch_state import set_state

    task = delete_batch_async.delay(user_id=current_user.id, doorway_ids=ids)
    set_state(task.id, {"user_id": current_user.id})
    return {"status": "queued", "task_id": task.id, "doorway_ids": ids}


@router.get("/batch-delete/{task_id}/status")
async def batch_delete_status(
    task_id: str,
    current_user: CurrentUser,
):
    """Get batch delete progress."""
    import asyncio
    from app.services.delete_batch_state import get_state
    state = await asyncio.to_thread(get_state, task_id)
    if not state or state.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task_id,
        "status": state.get("status", "running"),
        "total": state.get("total", 0),
        "current_index": state.get("current_index", 0),
        "deleted": state.get("deleted", 0),
        "error": state.get("error"),
        "results": state.get("results") or [],
    }


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
    from app.services.anti_detection import check_content_quality, CODE_NO_URGENCY_SOCIAL_PROOF, CODE_NO_FAQ

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
        warning_codes = list(r.warning_codes)
        if not (campaign.affiliate_url or "").strip():
            errors.append("Кампания без affiliate URL — CTA не будет работать")
        cr = doorway.cloaking_rules or {}
        camp_settings = (campaign.affiliate_rules or {}).get("settings") or {}
        if not (cr.get("urgency_block") or camp_settings.get("urgency_block")) and not cr.get("social_proof"):
            warnings.append("Нет urgency или social proof — можно добавить в Конверсию")
            warning_codes.append((CODE_NO_URGENCY_SOCIAL_PROOF, "Нет urgency или social proof — можно добавить в Конверсию"))
        if not cr.get("faq_qa"):
            warnings.append("Нет FAQ — можно сгенерировать при создании дорвея")
            warning_codes.append((CODE_NO_FAQ, "Нет FAQ — можно сгенерировать при создании дорвея"))
        out.append({
            "doorway_id": doorway.id,
            "path": doorway.path,
            "title": (doorway.title or "")[:60],
            "ok": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "warning_codes": [{"code": c, "message": m} for c, m in warning_codes],
        })
    return {"results": out}


class BatchApplyWarningsRequest(BaseModel):
    doorway_ids: List[int]
    fix_codes: List[str]  # e.g. ["meta_short", "keyword_not_in_title", "no_urgency_social_proof", "no_faq"]


@router.post("/batch-apply-warnings")
async def batch_apply_warnings(
    data: BatchApplyWarningsRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Применить исправления по предупреждениям к выбранным дорвеям (один, несколько или все из отчёта)."""
    if not data.doorway_ids or not data.fix_codes:
        return {"applied": {}, "per_doorway": [], "errors": [], "message": "Нет дорвеев или типов исправлений"}
    try:
        from app.services.quality_fixes import batch_apply_warnings as do_batch_apply
        result = await do_batch_apply(db, data.doorway_ids, data.fix_codes, current_user.id)
        return result
    except Exception as e:
        return {
            "applied": {},
            "per_doorway": [],
            "errors": [str(e)],
            "message": "Ошибка применения",
        }
