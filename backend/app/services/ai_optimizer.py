"""AI Optimizer: recommendations, rollback, A/B winner selection."""

import json
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.doorway import Doorway, DoorwayMetrics, DoorwayVersion
from app.models.domain import Domain
from app.services.openai_service import openai_service
from app.services.settings_helpers import get_user_openai_key


async def get_recommendations(
    db: AsyncSession,
    doorway_id: int,
    days: int = 14,
) -> List[dict]:
    """Analyze doorway metrics and return AI recommendations."""
    r = await db.execute(
        select(Doorway, Campaign).join(Campaign).where(Doorway.id == doorway_id)
    )
    row = r.first()
    if not row:
        return []
    dw, camp = row
    since = datetime.utcnow() - timedelta(days=days)
    r2 = await db.execute(
        select(DoorwayMetrics)
        .where(DoorwayMetrics.doorway_id == doorway_id, DoorwayMetrics.date >= since)
        .order_by(DoorwayMetrics.date.desc())
    )
    metrics_list = list(r2.scalars().all())
    if not metrics_list:
        return [{"type": "info", "text": "Недостаточно данных. Соберите метрики за 7+ дней."}]

    total_imp = sum(m.impressions for m in metrics_list)
    total_clk = sum(m.clicks for m in metrics_list)
    total_conv = sum(m.conversions for m in metrics_list)
    total_rev = sum(m.revenue for m in metrics_list)
    avg_pos_list = [m.avg_position for m in metrics_list if m.avg_position]
    avg_pos = sum(avg_pos_list) / len(avg_pos_list) if avg_pos_list else 0
    ctr = (total_clk / total_imp * 100) if total_imp else 0
    cr = (total_conv / total_clk * 100) if total_clk else 0

    if not openai_service.is_available():
        recs = []
        if ctr < 2 and total_imp > 100:
            recs.append({"type": "ctr", "text": "Низкий CTR. Улучшите title и meta."})
        if cr < 1 and total_clk > 50:
            recs.append({"type": "cr", "text": "Низкая CR. Проверьте CTA и оффер."})
        if avg_pos > 10 and total_imp > 0:
            recs.append({"type": "position", "text": f"Позиция {avg_pos:.1f}. Добавьте контент."})
        return recs or [{"type": "info", "text": "Метрики в норме."}]

    prompt = f"""Дорвей title="{dw.title}". Метрики: показы={total_imp}, клики={total_clk}, CTR={ctr:.2f}%, конв={total_conv}, CR={cr:.2f}%, выручка={total_rev:.2f}, ср.позиция={avg_pos:.1f}.
Дай 1-3 рекомендации. JSON: [{{"type":"ctr|cr|position|content","text":"..."}}]"""
    try:
        client = openai_service.get_client_for_key(user_openai_key)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        text = (resp.choices[0].message.content or "[]").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        return [{"type": "info", "text": "Анализ недоступен."}]


async def rollback_doorway(db: AsyncSession, doorway_id: int) -> tuple:
    """Rollback to previous version. Returns (success, message)."""
    r = await db.execute(
        select(DoorwayVersion)
        .where(DoorwayVersion.doorway_id == doorway_id)
        .order_by(DoorwayVersion.created_at.desc())
        .limit(2)
    )
    versions = list(r.scalars().all())
    if len(versions) < 2:
        return False, "Нет предыдущей версии"
    prev = versions[1]
    snap = prev.content_snapshot
    if not isinstance(snap, dict):
        return False, "Неверный формат"
    r2 = await db.execute(select(Doorway).where(Doorway.id == doorway_id))
    dw = r2.scalar_one_or_none()
    if not dw:
        return False, "Doorway не найден"
    dw.title = snap.get("title", dw.title)
    dw.content = snap.get("content", dw.content)
    dw.meta_description = snap.get("meta_description", dw.meta_description)
    await db.commit()
    return True, "Откат выполнен"


async def get_ab_winner(
    db: AsyncSession,
    campaign_id: int,
    days: int = 14,
    num_variants: int = 3,
) -> dict:
    """
    Compare layout variants across campaign doorways. Each doorway has a layout
    determined by hash(domain, path, id). Returns best variant and stats.
    """
    from app.services.anti_detection import get_layout_variant

    since = datetime.utcnow() - timedelta(days=days)
    r = await db.execute(
        select(Doorway, Domain)
        .join(Domain, Doorway.domain_id == Domain.id)
        .where(Doorway.campaign_id == campaign_id)
    )
    rows = r.all()
    if not rows:
        return {"winner": None, "variants": [], "message": "Нет дорвеев в кампании"}

    # Aggregate metrics per layout variant
    variant_stats: dict[int, dict] = {i: {"clicks": 0, "conversions": 0, "revenue": 0.0, "doorways": 0} for i in range(num_variants)}
    for dw, dom in rows:
        domain = dom.domain or ""
        path = (dw.path or "/").strip() or "/"
        layout_idx = get_layout_variant(domain, path, dw.id, num_variants)
        r2 = await db.execute(
            select(
                func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clk"),
                func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conv"),
                func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("rev"),
            ).where(DoorwayMetrics.doorway_id == dw.id, DoorwayMetrics.date >= since)
        )
        row2 = r2.first()
        if row2:
            variant_stats[layout_idx]["clicks"] += int(row2.clk or 0)
            variant_stats[layout_idx]["conversions"] += int(row2.conv or 0)
            variant_stats[layout_idx]["revenue"] += float(row2.rev or 0)
        variant_stats[layout_idx]["doorways"] += 1

    variants = []
    for i in range(num_variants):
        s = variant_stats[i]
        cr = (s["conversions"] / s["clicks"] * 100) if s["clicks"] else 0
        variants.append({
            "layout_index": i,
            "clicks": s["clicks"],
            "conversions": s["conversions"],
            "revenue": s["revenue"],
            "cr_percent": round(cr, 2),
            "doorways_count": s["doorways"],
        })

    # Winner: best CR with min 20 clicks, else best revenue
    candidates = [v for v in variants if v["clicks"] >= 20]
    if not candidates:
        candidates = [v for v in variants if v["clicks"] >= 5]
    if not candidates:
        return {"winner": None, "variants": variants, "message": "Недостаточно данных (min 5 кликов на вариант)"}

    best = max(candidates, key=lambda x: (x["cr_percent"], x["revenue"]))
    return {
        "winner": best["layout_index"],
        "winner_cr": best["cr_percent"],
        "winner_revenue": best["revenue"],
        "variants": variants,
        "message": f"Лучший layout: {best['layout_index']} (CR={best['cr_percent']}%, revenue={best['revenue']:.2f})",
    }


async def apply_recommendation(
    db: AsyncSession,
    doorway_id: int,
    rec_type: str,
    rec_text: str,
) -> tuple[bool, str, dict | None]:
    """
    Apply AI-generated fix for a recommendation.
    rec_type: ctr | cr | position | content
    Returns (success, message, updated_fields).
    """
    r = await db.execute(
        select(Doorway, Campaign).join(Campaign).where(Doorway.id == doorway_id)
    )
    row = r.first()
    if not row:
        return False, "Doorway не найден", None
    dw, camp = row

    if not openai_service.is_available():
        return False, "OpenAI недоступен", None

    prompt = f"""Дорвей: title="{dw.title}", meta="{dw.meta_description or ''}", content (начало): "{str(dw.content or '')[:500]}".
Рекомендация: {rec_text} (тип: {rec_type}).
Сгенерируй улучшенную версию. Ответ — JSON: {{"title":"...", "meta_description":"...", "content":"..."}}
- title: до 60 символов, цепляющий
- meta_description: до 160 символов
- content: полный HTML (все абзацы, H1, структура). Сохраняй тему и стиль."""

    try:
        client = openai_service.get_client_for_key(user_openai_key)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )
        text = (resp.choices[0].message.content or "{}").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text)
    except Exception as e:
        return False, f"Ошибка генерации: {e}", None

    # Save version for rollback
    snap = {
        "title": dw.title,
        "content": dw.content,
        "meta_description": dw.meta_description,
    }
    ver = DoorwayVersion(doorway_id=dw.id, content_snapshot=snap)
    db.add(ver)

    updated = {}
    if data.get("title"):
        dw.title = data["title"][:255]
        updated["title"] = dw.title
    if data.get("meta_description") is not None:
        dw.meta_description = data["meta_description"][:500] if data["meta_description"] else None
        updated["meta_description"] = dw.meta_description
    if data.get("content"):
        dw.content = data["content"]
        updated["content"] = dw.content

    await db.commit()
    return True, "Авто-правка применена", updated
