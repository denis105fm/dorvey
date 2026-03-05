"""Apply quality warning fixes to doorways (meta, keyword, urgency, FAQ)."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.doorway import Doorway
from app.models.campaign import Campaign
from app.models.keyword import Keyword
from app.services.anti_detection import (
    CODE_META_SHORT,
    CODE_KEYWORD_NOT_IN_TITLE,
    CODE_KEYWORD_NOT_IN_CONTENT,
    CODE_NO_URGENCY_SOCIAL_PROOF,
    CODE_NO_FAQ,
    MIN_DESCRIPTION_LENGTH,
)
from app.services.schema_helper import get_urgency_preset, get_social_proof_preset


async def _get_keyword_for_doorway(db: AsyncSession, campaign_id: int) -> str | None:
    r = await db.execute(
        select(Keyword.keyword).where(Keyword.campaign_id == campaign_id).limit(1)
    )
    row = r.first()
    return (row[0] or "").strip() or None


def _fix_meta_short(meta: str, keyword: str | None) -> str:
    """Extend meta to MIN_DESCRIPTION_LENGTH+ without AI."""
    meta = (meta or "").strip()
    if len(meta) >= MIN_DESCRIPTION_LENGTH:
        return meta
    suffix = " Узнайте подробнее."
    if keyword:
        suffix = f" {keyword}. Узнайте больше."
    while len(meta + suffix) < MIN_DESCRIPTION_LENGTH:
        suffix += " Выгодные условия."
    return (meta + suffix)[:160]


def _fix_keyword_in_title(title: str, keyword: str) -> str:
    """Ensure keyword in title (prepend or append)."""
    title = (title or "").strip()
    kw = (keyword or "").strip()
    if not kw or kw.lower() in (title or "").lower():
        return title
    if len(title) + len(kw) + 3 <= 60:
        return f"{kw} — {title}"
    return f"{title} | {kw}"[:70]


def _fix_keyword_in_content(content: str, keyword: str) -> str:
    """Inject keyword in first paragraph if missing."""
    content = (content or "").strip()
    kw = (keyword or "").strip()
    if not kw or kw.lower() in content.lower():
        return content
    first_p_end = content.find("</p>")
    if first_p_end != -1:
        insert_pos = first_p_end + 4
        sentence = f" <p>{kw} — актуальная тема для многих.</p>"
        return content[:insert_pos] + sentence + content[insert_pos:]
    if content.startswith("<h1>"):
        end_h1 = content.find("</h1>")
        if end_h1 != -1:
            insert_pos = end_h1 + 5
            sentence = f"<p>{kw}.</p>"
            return content[:insert_pos] + sentence + content[insert_pos:]
    return content + f"<p>{kw}.</p>"


async def apply_fixes_to_doorway(
    db: AsyncSession,
    doorway_id: int,
    fix_codes: list[str],
    user_id: int,
) -> dict[str, int]:
    """Apply given fix codes to one doorway. Returns counts per code applied."""
    r = await db.execute(
        select(Doorway, Campaign)
        .join(Campaign, Doorway.campaign_id == Campaign.id)
        .where(Doorway.id == doorway_id, Campaign.user_id == user_id)
    )
    row = r.first()
    if not row:
        return {}
    doorway, campaign = row
    keyword = await _get_keyword_for_doorway(db, doorway.campaign_id)
    if not keyword:
        keyword = ((doorway.title or "").strip().split()[0] if doorway.title else None)
    applied: dict[str, int] = {}

    if CODE_META_SHORT in fix_codes and doorway.meta_description and len((doorway.meta_description or "").strip()) < MIN_DESCRIPTION_LENGTH:
        doorway.meta_description = _fix_meta_short(doorway.meta_description or "", keyword)
        applied[CODE_META_SHORT] = 1

    if CODE_KEYWORD_NOT_IN_TITLE in fix_codes and keyword and doorway.title and keyword.lower() not in (doorway.title or "").lower():
        doorway.title = _fix_keyword_in_title(doorway.title or "", keyword)
        applied[CODE_KEYWORD_NOT_IN_TITLE] = 1

    if CODE_KEYWORD_NOT_IN_CONTENT in fix_codes and keyword and doorway.content and keyword.lower() not in (doorway.content or "").lower():
        doorway.content = _fix_keyword_in_content(doorway.content or "", keyword)
        applied[CODE_KEYWORD_NOT_IN_CONTENT] = 1

    if CODE_NO_URGENCY_SOCIAL_PROOF in fix_codes:
        cr = dict(doorway.cloaking_rules or {})
        camp_settings = (campaign.affiliate_rules or {}).get("settings") or {}
        if not cr.get("urgency_block") and not camp_settings.get("urgency_block"):
            preset = get_urgency_preset(campaign.language or "en", doorway.id)
            if preset:
                cr["urgency_block"] = {"text": preset}
        if not cr.get("social_proof"):
            preset = get_social_proof_preset(campaign.language or "ru", doorway.id)
            if preset:
                cr["social_proof"] = preset
        if cr != (doorway.cloaking_rules or {}):
            doorway.cloaking_rules = cr
            applied[CODE_NO_URGENCY_SOCIAL_PROOF] = 1

    if CODE_NO_FAQ in fix_codes:
        cr = dict(doorway.cloaking_rules or {})
        if not cr.get("faq_qa"):
            from app.services.openai_service import openai_service
            from app.services.settings_helpers import get_user_openai_key
            api_key = await get_user_openai_key(db, campaign.user_id)
            if openai_service.is_available(api_key):
                kw = keyword or (doorway.title or "").strip()[:50] or "topic"
                faq_qa = await openai_service.generate_faq(
                    keyword=kw,
                    language=campaign.language or "en",
                    max_items=6,
                    api_key_override=api_key,
                )
                if faq_qa:
                    cr["faq_qa"] = faq_qa
                    doorway.cloaking_rules = cr
                    applied[CODE_NO_FAQ] = 1

    return applied


async def batch_apply_warnings(
    db: AsyncSession,
    doorway_ids: list[int],
    fix_codes: list[str],
    user_id: int,
) -> dict:
    """Apply fix_codes to each doorway. Returns applied counts, per_doorway, errors."""
    if not doorway_ids or not fix_codes:
        return {"applied": {}, "per_doorway": [], "errors": []}
    total_applied: dict[str, int] = {}
    per_doorway: list[dict] = []
    errors: list[str] = []
    for dw_id in doorway_ids:
        try:
            applied = await apply_fixes_to_doorway(db, dw_id, fix_codes, user_id)
            for code, count in applied.items():
                total_applied[code] = total_applied.get(code, 0) + count
            per_doorway.append({"doorway_id": dw_id, "applied": applied})
        except Exception as e:
            errors.append(f"Doorway {dw_id}: {str(e)[:100]}")
    await db.commit()
    return {"applied": total_applied, "per_doorway": per_doorway, "errors": errors}
