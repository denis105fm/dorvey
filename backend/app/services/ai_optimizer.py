"""AI Optimizer: recommendations, rollback, A/B winner selection."""

import hashlib
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

    user_openai_key = await get_user_openai_key(db, camp.user_id)
    if not openai_service.is_available(user_openai_key):
        recs = []
        if ctr < 2 and total_imp > 100:
            recs.append({"type": "ctr", "text": "Низкий CTR. Улучшите title и meta."})
        if cr < 1 and total_clk > 50:
            recs.append({"type": "cr", "text": "Низкая CR. Проверьте CTA и оффер."})
        if avg_pos > 10 and total_imp > 0:
            recs.append({"type": "position", "text": f"Позиция {avg_pos:.1f}. Добавьте контент."})
        applied_hashes = set(dw.applied_recommendation_hashes or [])
        recs = [r for r in recs if _rec_hash(r.get("text") or "") not in applied_hashes]
        return recs or [{"type": "info", "text": "Метрики в норме."}]

    prompt = f"""Дорвей title="{dw.title}". Метрики: показы={total_imp}, клики={total_clk}, CTR={ctr:.2f}%, конв={total_conv}, CR={cr:.2f}%, выручка={total_rev:.2f}, ср.позиция={avg_pos:.1f}.
Дай 1-3 конкретные рекомендации по улучшению. Учитывай: низкий CTR — улучшить title/meta; низкая CR — проверить CTA и оффер; слабая позиция — больше контента.
JSON: [{{"type":"ctr|cr|position|content","text":"конкретный совет"}}]"""
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
        recs = json.loads(text)
    except Exception:
        return [{"type": "info", "text": "Анализ недоступен."}]

    # Don't suggest recommendations that were already applied
    applied_hashes = set(dw.applied_recommendation_hashes or [])
    filtered = [r for r in (recs if isinstance(recs, list) else []) if _rec_hash(r.get("text") or "") not in applied_hashes]
    return filtered if filtered else [{"type": "info", "text": "Все предыдущие рекомендации применены. Метрики в норме или соберите больше данных."}]


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

    user_openai_key = await get_user_openai_key(db, camp.user_id)
    if not openai_service.is_available(user_openai_key):
        return False, "OpenAI недоступен", None

    prompt = f"""Дорвей: title="{dw.title}", meta="{dw.meta_description or ''}", content (начало): "{str(dw.content or '')[:500]}".
Рекомендация: {rec_text} (тип: {rec_type}).
Сгенерируй улучшенную версию. Сохраняй тему, тон и объём. Без шаблонных фраз.
JSON: {{"title":"...", "meta_description":"...", "content":"..."}}
- title: 50-60 символов, цепляющий
- meta_description: 140-160 символов
- content: полный HTML, H1 + параграфы <p>, минимум 400 слов"""

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

    # Remember this recommendation so we don't suggest it again
    hashes = list(dw.applied_recommendation_hashes or [])
    h = _rec_hash(rec_text)
    if h not in hashes:
        hashes.append(h)
        dw.applied_recommendation_hashes = hashes

    await db.commit()
    return True, "Авто-правка применена", updated


async def copy_winner_to_doorway(
    db: AsyncSession,
    source_doorway_id: int,
    target_doorway_id: int,
    user_id: int,
) -> tuple[bool, str]:
    """
    Copy content (title, content, meta_description) from winning doorway to target.
    Both must belong to user's campaigns.
    """
    r = await db.execute(
        select(Doorway, Campaign.user_id)
        .join(Campaign)
        .where(
            Doorway.id.in_([source_doorway_id, target_doorway_id]),
            Campaign.user_id == user_id,
        )
    )
    rows = {row[0].id: (row[0], row[1]) for row in r.all()}
    if source_doorway_id not in rows or target_doorway_id not in rows:
        return False, "Doorway не найден или нет доступа"
    src = rows[source_doorway_id][0]
    tgt = rows[target_doorway_id][0]

    # Save target version for rollback
    snap = {
        "title": tgt.title,
        "content": tgt.content,
        "meta_description": tgt.meta_description,
    }
    db.add(DoorwayVersion(doorway_id=tgt.id, content_snapshot=snap))

    tgt.title = src.title
    tgt.content = src.content
    tgt.meta_description = src.meta_description
    await db.commit()
    return True, f"Контент скопирован с дорвея #{source_doorway_id}"


async def get_best_doorway_by_cr(
    db: AsyncSession,
    campaign_id: int,
    user_id: int,
    min_clicks: int = 20,
    days: int = 14,
) -> Optional[int]:
    """
    Find doorway with best CR in campaign (min_clicks required).
    Returns doorway_id or None.
    """
    since = datetime.utcnow() - timedelta(days=days)
    subq = select(Doorway.id).join(Campaign).where(
        Doorway.campaign_id == campaign_id, Campaign.user_id == user_id
    )
    r = await db.execute(
        select(
            DoorwayMetrics.doorway_id,
            func.coalesce(func.sum(DoorwayMetrics.clicks), 0).label("clk"),
            func.coalesce(func.sum(DoorwayMetrics.conversions), 0).label("conv"),
            func.coalesce(func.sum(DoorwayMetrics.revenue), 0).label("rev"),
        )
        .where(
            DoorwayMetrics.doorway_id.in_(subq),
            DoorwayMetrics.date >= since,
        )
        .group_by(DoorwayMetrics.doorway_id)
    )
    candidates = []
    for row in r.all():
        if row.clk and row.clk >= min_clicks:
            cr = (row.conv or 0) / row.clk * 100
            candidates.append((row.doorway_id, cr, row.rev or 0, row.clk))
    if not candidates:
        return None
    best = max(candidates, key=lambda x: (x[1], x[2]))
    return best[0]


async def get_pause_recommendations(
    db: AsyncSession,
    doorway_id: int,
    user_id: int,
    days: int = 14,
    num_variants: int = 3,
) -> List[dict]:
    """
    Рекомендации для дорвея на паузе: на основе прибыльных дорвеев кампании —
    какой layout/вариант даёт лучший CR, предложить применить его.
    """
    from app.services.anti_detection import get_layout_variant

    r = await db.execute(
        select(Doorway, Domain, Campaign)
        .join(Domain, Doorway.domain_id == Domain.id)
        .join(Campaign, Doorway.campaign_id == Campaign.id)
        .where(Doorway.id == doorway_id, Campaign.user_id == user_id)
    )
    row = r.first()
    if not row:
        return []
    dw, dom, camp = row
    if dw.status != "paused":
        return [{"type": "info", "text": "Дорвей не на паузе. Рекомендации после паузы показываются для дорвеев со статусом «На паузе»."}]

    ab = await get_ab_winner(db, camp.id, days=days, num_variants=num_variants)
    if ab.get("winner") is None:
        return [{"type": "info", "text": "Недостаточно данных по кампании для рекомендации (нужен трафик по вариантам A/B)."}]
    winner_idx = ab["winner"]
    winner_cr = ab.get("winner_cr") or 0
    winner_revenue = ab.get("winner_revenue") or 0
    domain = dom.domain or ""
    path = (dw.path or "/").strip() or "/"
    current_layout = get_layout_variant(domain, path, dw.id, num_variants)
    variants = ab.get("variants") or []

    suggestions = []
    if current_layout != winner_idx:
        suggestions.append({
            "type": "suggestion",
            "text": f"В кампании «{camp.name or camp.id}» лучший результат у варианта {winner_idx} (CR {winner_cr}%, выручка {winner_revenue:.2f}). Ваш дорвей сейчас на варианте {current_layout}. Рекомендуем применить вариант {winner_idx} в блоке A/B.",
            "layout_index": winner_idx,
            "winner_cr": winner_cr,
            "winner_revenue": winner_revenue,
        })
    else:
        suggestions.append({
            "type": "info",
            "text": f"Ваш дорвей уже использует вариант {winner_idx}, который в кампании даёт лучший CR ({winner_cr}%). Проверьте оффер и постбек.",
        })
    if variants:
        suggestions.append({
            "type": "data",
            "variants": variants,
        })
    return suggestions
