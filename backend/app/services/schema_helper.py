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
]

TRUST_VARIANTS_EN = [
    '<span>🔒 Secure</span><span>✓ Verified</span><span>⚡ Fast</span>',
    '<span>✓ Verified</span><span>🔒 Secure</span><span>⚡ Fast</span>',
    '<span>⚡ Fast</span><span>✓ Verified</span><span>🔒 Secure</span>',
]


def build_trust_elements_html(lang: str = "ru", seed: Optional[int] = None) -> str:
    """Trust badges HTML. Variants reduce structural fingerprint."""
    variants = TRUST_VARIANTS_RU if lang == "ru" else TRUST_VARIANTS_EN
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
