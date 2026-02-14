"""Cloaking: bot vs human detection."""

from typing import Optional, List

DEFAULT_BOT_PATTERNS = [
    "Googlebot", "YandexBot", "Yandex", "bingbot", "BingPreview",
    "Slurp", "DuckDuckBot", "Baiduspider", "facebookexternalhit",
    "Twitterbot", "LinkedInBot", "TelegramBot", "Applebot",
]


def is_bot(user_agent: Optional[str], bot_patterns: Optional[List[str]] = None) -> bool:
    if not user_agent:
        return False
    patterns = bot_patterns or DEFAULT_BOT_PATTERNS
    ua = user_agent.lower()
    return any(p.lower() in ua for p in patterns)
