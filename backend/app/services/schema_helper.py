"""JSON-LD schema helpers for Featured Snippets, PAA, SEO."""

import json
import random
from typing import Optional


def build_article_schema(
    title: str,
    description: str,
    url: str,
    date_published: Optional[str] = None,
) -> str:
    """Build WebPage/Article schema for rich snippets."""
    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title[:110],
        "description": description[:160] if description else "",
        "url": url,
    }
    if date_published:
        schema["datePublished"] = date_published
    return json.dumps(schema, ensure_ascii=False)


def build_faq_schema(questions_answers: list[dict]) -> str:
    """Build FAQPage schema from list of {question, answer}."""
    if not questions_answers:
        return ""
    items = []
    for qa in questions_answers[:10]:  # max 10 for schema
        q = qa.get("question", "").strip()
        a = qa.get("answer", "").strip()
        if q and a:
            items.append({
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {
                    "@type": "Answer",
                    "text": a,
                },
            })
    if not items:
        return ""
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": items,
    }
    return json.dumps(schema, ensure_ascii=False)


TRUST_VARIANTS_RU = [
    '<span>🔒 Безопасно</span><span>✓ Проверено</span><span>⚡ Быстро</span>',
    '<span>✓ Проверено</span><span>🔒 Безопасно</span><span>⚡ Быстро</span>',
    '<span>⚡ Быстро</span><span>✓ Проверено</span><span>🔒 Безопасно</span>',
    '<span class="badge">🔒 Безопасно</span><span class="badge">✓ Проверено</span>',
    '<span>Официальный партнёр</span><span>✓ Одобрено</span><span>Служба поддержки 24/7</span>',
    '<span>✓ Лучшие условия</span><span>Проверенные данные</span><span>Без скрытых комиссий</span>',
    '<span>Свыше 50 000 клиентов</span><span>✓ Рекомендовано экспертами</span><span>Бесплатная консультация</span>',
    '<span>✓ Лучшая цена</span><span>Гарантия возврата</span><span>Быстрое оформление</span>',
]

TRUST_VARIANTS_EN = [
    '<span>🔒 Secure</span><span>✓ Verified</span><span>⚡ Fast</span>',
    '<span>✓ Verified</span><span>🔒 Secure</span><span>⚡ Fast</span>',
    '<span>⚡ Fast</span><span>✓ Verified</span><span>🔒 Secure</span>',
    '<span class="badge">🔒 Secure</span><span class="badge">✓ Verified</span>',
    '<span>Official Partner</span><span>✓ Approved</span><span>24/7 Support</span>',
    '<span>✓ Best Rates</span><span>Verified Data</span><span>No Hidden Fees</span>',
    '<span>50,000+ Customers</span><span>✓ Expert Recommended</span><span>Free Consultation</span>',
]

TRUST_VARIANTS_DE = [
    '<span>🔒 Sicher</span><span>✓ Geprüft</span><span>⚡ Schnell</span>',
    '<span>✓ Geprüft</span><span>🔒 Sicher</span><span>24/7 Support</span>',
    '<span>Offizieller Partner</span><span>✓ Empfohlen</span>',
]

TRUST_VARIANTS_ES = [
    '<span>🔒 Seguro</span><span>✓ Verificado</span><span>⚡ Rápido</span>',
    '<span>✓ Verificado</span><span>Soporte 24/7</span><span>Sin comisiones ocultas</span>',
]

TRUST_VARIANTS_PL = [
    '<span>🔒 Bezpiecznie</span><span>✓ Zweryfikowane</span><span>⚡ Szybko</span>',
    '<span>✓ Sprawdzone</span><span>Oficjalny partner</span>',
]

TRUST_BY_LANG = {
    "ru": TRUST_VARIANTS_RU, "en": TRUST_VARIANTS_EN,
    "de": TRUST_VARIANTS_DE, "es": TRUST_VARIANTS_ES, "pl": TRUST_VARIANTS_PL,
}

# Psychological conversion presets: urgency, scarcity, FOMO
URGENCY_PRESETS_RU = [
    "Одобрение за 5 минут • Без отказа",
    "Специальные условия — ограничено по времени",
    "Осталось 3 места по этой ставке",
    "12 человек уже оформили сегодня",
    "Акция до конца недели",
    "Сравните и выберите лучшее предложение",
]
URGENCY_PRESETS_EN = [
    "Approval in 5 minutes • No refusal",
    "Limited time offer",
    "Only 3 spots left at this rate",
    "15 people applied today",
    "Offer ends this week",
    "Compare and choose the best deal",
]
URGENCY_PRESETS_DE = [
    "Zusage in 5 Minuten",
    "Nur noch 3 Plätze zu diesem Zinssatz",
    "Angebot befristet",
]
URGENCY_BY_LANG = {"ru": URGENCY_PRESETS_RU, "en": URGENCY_PRESETS_EN, "de": URGENCY_PRESETS_DE}
URGENCY_BY_LANG.setdefault("es", URGENCY_PRESETS_EN)
URGENCY_BY_LANG.setdefault("pl", URGENCY_PRESETS_EN)

# Social proof presets (stats + short reviews)
SOCIAL_PROOF_PRESETS_RU = [
    {"stats": "Свыше 50 000 одобренных заявок", "reviews": ["Быстро и без лишних документов", "Одобрили с первого раза"]},
    {"stats": "12 000+ клиентов в этом месяце", "reviews": ["Прозрачные условия", "Рекомендую"]},
    {"stats": "Рейтинг 4.8 из 5", "reviews": ["Удобный сервис", "Помогли с выбором"]},
]
SOCIAL_PROOF_PRESETS_EN = [
    {"stats": "50,000+ applications approved", "reviews": ["Fast and hassle-free", "Approved on first try"]},
    {"stats": "12,000+ customers this month", "reviews": ["Transparent terms", "Recommended"]},
]
SOCIAL_PROOF_BY_LANG = {"ru": SOCIAL_PROOF_PRESETS_RU, "en": SOCIAL_PROOF_PRESETS_EN}
SOCIAL_PROOF_BY_LANG.setdefault("de", SOCIAL_PROOF_PRESETS_EN)
SOCIAL_PROOF_BY_LANG.setdefault("es", SOCIAL_PROOF_PRESETS_EN)
SOCIAL_PROOF_BY_LANG.setdefault("pl", SOCIAL_PROOF_PRESETS_EN)

# Exit intent presets
EXIT_INTENT_PRESETS_RU = [
    {"title": "Подождите! Специальное предложение для вас", "cta": "Получить скидку"},
    {"title": "Не упустите выгодные условия", "cta": "Оформить заявку"},
    {"title": "Осталось всего 2 минуты — получите бонус", "cta": "Перейти"},
]
EXIT_INTENT_PRESETS_EN = [
    {"title": "Wait! Special offer for you", "cta": "Get discount"},
    {"title": "Don't miss out on great rates", "cta": "Apply now"},
]
EXIT_INTENT_BY_LANG = {"ru": EXIT_INTENT_PRESETS_RU, "en": EXIT_INTENT_PRESETS_EN}
EXIT_INTENT_BY_LANG.setdefault("de", EXIT_INTENT_PRESETS_EN)
EXIT_INTENT_BY_LANG.setdefault("es", EXIT_INTENT_PRESETS_EN)

# CTA text presets (desktop, mobile)
CTA_PRESETS_RU = [
    {"desktop": "Оформить заявку", "mobile": "Оформить"},
    {"desktop": "Узнать условия", "mobile": "Подробнее"},
    {"desktop": "Получить предложение", "mobile": "Получить"},
    {"desktop": "Перейти к сравнению", "mobile": "Сравнить"},
]
CTA_PRESETS_EN = [
    {"desktop": "Apply now", "mobile": "Apply"},
    {"desktop": "Get offer", "mobile": "Get"},
    {"desktop": "Compare options", "mobile": "Compare"},
]
CTA_BY_LANG = {"ru": CTA_PRESETS_RU, "en": CTA_PRESETS_EN}
CTA_BY_LANG.setdefault("de", CTA_PRESETS_EN)
CTA_BY_LANG.setdefault("es", CTA_PRESETS_EN)
CTA_BY_LANG.setdefault("pl", CTA_PRESETS_EN)


def get_urgency_preset(lang: str, seed: int) -> str:
    """Return urgency block text from presets. Deterministic by seed. Default lang: en."""
    variants = URGENCY_BY_LANG.get((lang or "en").lower()[:2], URGENCY_PRESETS_EN)
    return variants[seed % len(variants)]


def get_social_proof_preset(lang: str, seed: int) -> dict:
    """Return social_proof dict from presets. Default lang: en."""
    variants = SOCIAL_PROOF_BY_LANG.get((lang or "en").lower()[:2], SOCIAL_PROOF_PRESETS_EN)
    return variants[seed % len(variants)]


def get_exit_intent_preset(lang: str, seed: int) -> dict:
    """Return exit_intent dict from presets. Default lang: en."""
    variants = EXIT_INTENT_BY_LANG.get((lang or "en").lower()[:2], EXIT_INTENT_PRESETS_EN)
    return variants[seed % len(variants)]


def get_cta_preset(lang: str, seed: int) -> dict:
    """Return cta_by_device dict from presets. Default lang: en."""
    variants = CTA_BY_LANG.get((lang or "en").lower()[:2], CTA_PRESETS_EN)
    return variants[seed % len(variants)]


# UI strings for doorway page: table, push, email, defaults (by language)
DOORWAY_UI_RU = {
    "table_name": "Название",
    "table_rate": "Ставка",
    "table_amount": "Сумма",
    "table_term": "Срок",
    "table_apply": "Оформить",
    "option_label": "Вариант",
    "default_cta": "Узнать подробнее",
    "exit_default_title": "Подождите! Специальное предложение для вас",
    "exit_default_cta": "Получить скидку",
    "push_title": "🔥 Не пропустите выгодное предложение!",
    "push_desc": "Разрешите уведомления — первыми узнаете о скидках и специальных условиях.",
    "push_btn": "Разрешить уведомления",
    "push_subscribe_btn": "🔔 Подписаться на уведомления",
    "push_later": "Позже",
    "push_loading": "Загрузка...",
    "push_done": "✓ Готово!",
    "push_denied": "Разрешение не дано",
    "push_subscribed": "✓ Вы подписаны",
    "email_title": "📧 Получите персональное предложение",
    "email_desc": "Оставьте email — пришлём выгодные условия.",
    "email_placeholder": "Email для получения предложения",
    "email_btn": "Получить предложение",
    "email_btn_short": "Отправить",
    "email_later": "Позже",
    "email_sending": "Отправка...",
    "email_done": "✓ Готово! Спасибо.",
    "email_error": "Ошибка",
    "email_required": "Введите email",
    "quiz_title": "Подберите подходящий вариант",
    "quiz_next": "Далее",
    "quiz_submit": "Перейти к предложению",
    "faq_heading": "Часто спрашивают",
    "internal_links_heading": "Ещё по теме",
}
DOORWAY_UI_EN = {
    "table_name": "Name",
    "table_rate": "Rate",
    "table_amount": "Amount",
    "table_term": "Term",
    "table_apply": "Apply",
    "option_label": "Option",
    "default_cta": "Learn more",
    "exit_default_title": "Wait! Special offer for you",
    "exit_default_cta": "Get discount",
    "push_title": "🔥 Don't miss out on great offers!",
    "push_desc": "Allow notifications — be the first to know about deals and special conditions.",
    "push_btn": "Allow notifications",
    "push_subscribe_btn": "🔔 Subscribe to notifications",
    "push_later": "Later",
    "push_loading": "Loading...",
    "push_done": "✓ Done!",
    "push_denied": "Permission denied",
    "push_subscribed": "✓ You're subscribed",
    "email_title": "📧 Get a personalized offer",
    "email_desc": "Leave your email — we'll send you the best conditions.",
    "email_placeholder": "Email for offers",
    "email_btn": "Get offer",
    "email_btn_short": "Submit",
    "email_later": "Later",
    "email_sending": "Sending...",
    "email_done": "✓ Done! Thank you.",
    "email_error": "Error",
    "email_required": "Enter your email",
    "quiz_title": "Find the right option for you",
    "quiz_next": "Next",
    "quiz_submit": "Go to offer",
    "faq_heading": "Frequently asked questions",
    "internal_links_heading": "Related topics",
}
DOORWAY_UI_BY_LANG = {"ru": DOORWAY_UI_RU, "en": DOORWAY_UI_EN}
for _k in ["de", "es", "pl", "fr", "pt"]:
    DOORWAY_UI_BY_LANG.setdefault(_k, DOORWAY_UI_EN)


def get_doorway_ui_strings(lang: str) -> dict:
    """Return localized UI strings for doorway page (table, push, email, defaults). Fallback: en for non-ru."""
    key = (lang or "en").lower()[:2]
    return DOORWAY_UI_BY_LANG.get(key, DOORWAY_UI_EN).copy()


def build_trust_elements_html(lang: str = "en", seed: Optional[int] = None) -> str:
    """Trust badges HTML. Variants reduce structural fingerprint. Default lang: en."""
    lang_key = (lang or "en").lower()[:2]
    variants = TRUST_BY_LANG.get(lang_key, TRUST_VARIANTS_EN)
    if seed is not None:
        return variants[seed % len(variants)]
    return random.choice(variants)


def build_webpage_schema(title: str, description: str, url: str) -> str:
    """WebPage schema (alternative to Article for variation)."""
    schema = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title[:110],
        "description": description[:160] if description else "",
        "url": url,
    }
    return json.dumps(schema, ensure_ascii=False)


def build_paa_schema(questions_answers: list[dict]) -> str:
    """
    People Also Ask (PAA) — same as FAQ schema for rich results.
    Use distinct Q&A pairs for PAA targeting.
    """
    return build_faq_schema(questions_answers)
