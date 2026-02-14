"""Telegram notifications."""

import httpx
from typing import Optional
from app.core.config import settings


async def send_telegram(
    text: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    """Send message to Telegram. Uses user settings or env fallback."""
    token = bot_token or settings.TELEGRAM_BOT_TOKEN
    cid = chat_id or settings.TELEGRAM_CHAT_ID
    if not token or not cid:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json={"chat_id": cid, "text": text})
            return 200 <= r.status_code < 300
    except Exception:
        return False
