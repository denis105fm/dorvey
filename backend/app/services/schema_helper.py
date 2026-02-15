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


def build_trust_elements_html(lang: str = "ru", seed: Optional[int] = None) -> str:
    """Trust badges HTML. Variants reduce structural fingerprint."""
    lang_key = (lang or "ru").lower()[:2]
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
