"""Doorway content generator: AI + templates + validation."""

import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.campaign import Campaign
from app.models.domain import Domain
from app.models.offer import Offer
from app.models.setting import Setting
from app.services.openai_service import openai_service
from app.services.settings_helpers import get_user_openai_key
from app.services.affiliate_validator import get_forbidden_words, validate_content
from app.services.template_engine import render_doorway_page


async def _load_external_settings(db: AsyncSession, user_id: int):
    """Returns (enabled, news_key, gnews_key, mstack_key, guardian_key, season_url)."""
    r = await db.execute(
        select(Setting).where(
            Setting.user_id == user_id,
            Setting.key.in_([
                "external_data_enabled", "news_api_key", "gnews_api_key",
                "mediastack_api_key", "guardian_api_key", "seasonality_data_url",
            ]),
        )
    )
    rows = {s.key: s.value for s in r.scalars().all()}
    enabled = (rows.get("external_data_enabled") or "").strip().lower() in ("true", "1")
    news_key = (rows.get("news_api_key") or "").strip() or None
    gnews_key = (rows.get("gnews_api_key") or "").strip() or None
    mstack_key = (rows.get("mediastack_api_key") or "").strip() or None
    guard_key = (rows.get("guardian_api_key") or "").strip() or None
    season_url = (rows.get("seasonality_data_url") or "").strip() or None
    return enabled, news_key, gnews_key, mstack_key, guard_key, season_url


def _build_external_context_hint(signals: dict) -> Optional[str]:
    """
    Build a short (2–3 lines max) hint for the AI from external signals.
    Only includes seasonality when relevant and up to 2 headlines. Returns None if nothing useful.
    """
    parts = []
    # Сезонность: подмешиваем только если есть и не ошибка, и коэффициент текущего месяца >= 1.0
    season = signals.get("seasonality")
    if isinstance(season, dict) and "error" not in season:
        month = datetime.datetime.utcnow().month
        coef = season.get(str(month)) or season.get("default")
        if coef is not None and float(coef) >= 1.05:
            parts.append("Сезонность: повышенный интерес в регионе в текущий период.")
        elif coef is not None and float(coef) >= 1.0:
            parts.append("Сезонность: стабильный спрос в регионе.")
    # Новости: максимум 2 заголовка, обрезаем длину
    news = signals.get("news") or {}
    headlines = (news.get("headlines") or [])[:2]
    if headlines:
        titles = []
        for h in headlines:
            t = (h.get("title") or "").strip() if isinstance(h, dict) else str(h).strip()
            if t:
                titles.append(t[:60] + ("…" if len(t) > 60 else ""))
        if titles:
            parts.append("Актуальные темы в регионе: " + "; ".join(titles) + ".")
    if not parts:
        return None
    return "\n".join(parts)


async def generate_doorway(
    db: AsyncSession,
    *,
    campaign_id: int,
    domain_id: int,
    keyword: str,
    path: str = "/",
    generate_faq: bool = False,
) -> dict:
    """
    Generate doorway content via AI, validate, render HTML.
    Returns dict with title, meta_description, content, html.
    """
    camp = (await db.execute(select(Campaign).where(Campaign.id == campaign_id))).scalar_one_or_none()
    if not camp:
        raise ValueError("Campaign not found")
    dom = (await db.execute(select(Domain).where(Domain.id == domain_id))).scalar_one_or_none()
    if not dom:
        raise ValueError("Domain not found")

    user_openai_key = await get_user_openai_key(db, camp.user_id)
    if not openai_service.is_available(user_openai_key):
        data = {
            "title": f"{keyword} | Лучшие предложения",
            "meta_description": f"Узнайте о {keyword}.",
            "content": f"<h1>{keyword}</h1><p>Информация по запросу {keyword}.</p>",
        }
        html = render_doorway_page(
            title=data["title"],
            meta_description=data["meta_description"],
            content=data["content"],
            language=camp.language,
            affiliate_url=camp.affiliate_url,
            canonical_url=f"https://{dom.domain}",
        )
        data["html"] = html
        return data

    forbidden = get_forbidden_words(camp.affiliate_rules)
    external_context: Optional[str] = None
    # Подмешиваем внешние данные только если включены в настройках (сезонность/новости — короткая подсказка)
    enabled, news_key, gnews_key, mstack_key, guard_key, season_url = await _load_external_settings(db, camp.user_id)
    if enabled:
        country_code = (camp.region or "").strip().lower()[:2] if getattr(camp, "region", None) else ""
        if not country_code:
            off_r = await db.execute(
                select(Offer.geo).where(Offer.campaign_id == camp.id, Offer.geo.isnot(None), Offer.geo != "").limit(1)
            )
            row = off_r.first()
            if row and row[0]:
                country_code = (row[0] or "").strip().lower()[:2]
        if country_code:
            from app.services.external_data_service import get_external_signals
            try:
                signals = await get_external_signals(
                    country_code=country_code,
                    days=7,
                    news_api_key=news_key,
                    gnews_api_key=gnews_key,
                    mediastack_api_key=mstack_key,
                    guardian_api_key=guard_key,
                    seasonality_data_url=season_url,
                )
                external_context = _build_external_context_hint(signals)
            except Exception:
                external_context = None
    data = await openai_service.generate_doorway_content(
        keyword=keyword,
        language=camp.language,
        region=camp.region,
        affiliate_url=camp.affiliate_url,
        forbidden_words=forbidden or None,
        external_context=external_context,
        api_key_override=user_openai_key,
    )

    ok, violations = validate_content(
        data.get("content", "") + data.get("title", "") + data.get("meta_description", ""),
        forbidden_words=forbidden,
    )
    if not ok:
        data["validation_violations"] = violations

    if generate_faq and openai_service.is_available(user_openai_key):
        faq_qa = await openai_service.generate_faq(
            keyword=keyword,
            language=camp.language,
            max_items=8,
            api_key_override=user_openai_key,
        )
        if faq_qa:
            data["faq_qa"] = faq_qa

    canonical = f"https://{dom.domain.rstrip('/')}{path}" if path != "/" else f"https://{dom.domain}"
    html = render_doorway_page(
        title=data.get("title", keyword),
        meta_description=data.get("meta_description", ""),
        content=data.get("content", ""),
        language=camp.language,
        affiliate_url=camp.affiliate_url,
        canonical_url=canonical,
    )
    data["html"] = html
    return data
