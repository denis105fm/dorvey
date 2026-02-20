"""Doorway content generator: AI + templates + validation."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.campaign import Campaign
from app.models.domain import Domain
from app.services.openai_service import openai_service
from app.services.settings_helpers import get_user_openai_key
from app.services.affiliate_validator import get_forbidden_words, validate_content
from app.services.template_engine import render_doorway_page


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
    data = await openai_service.generate_doorway_content(
        keyword=keyword,
        language=camp.language,
        region=camp.region,
        affiliate_url=camp.affiliate_url,
        forbidden_words=forbidden or None,
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
            max_items=5,
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
