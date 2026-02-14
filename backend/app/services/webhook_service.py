"""Webhook notifications."""

import asyncio
from typing import Any, Optional

import httpx


async def fire_webhook(url: str, payload: dict[str, Any], timeout: float = 5.0) -> Optional[bool]:
    """Send POST to webhook URL. Returns True on success."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=payload, timeout=timeout)
            return 200 <= r.status_code < 300
    except Exception:
        return None


async def send_telegram_if_configured(db, user_id: int, event: str, payload: dict) -> None:
    """Send to Telegram if user has it configured."""
    from sqlalchemy import select
    from app.models.setting import Setting
    from app.services.telegram_notify import send_telegram

    r = await db.execute(
        select(Setting).where(
            Setting.user_id == user_id,
            Setting.key.in_(["telegram_bot_token", "telegram_chat_id"]),
        )
    )
    rows = {s.key: s.value for s in r.scalars().all()}
    from app.core.config import settings as app_settings
    token = (rows.get("telegram_bot_token") or "").strip() or app_settings.TELEGRAM_BOT_TOKEN
    chat_id = (rows.get("telegram_chat_id") or "").strip() or app_settings.TELEGRAM_CHAT_ID
    if token and chat_id:
        text = f"Dorvey: {event}\n{payload}"
        await send_telegram(text, bot_token=token, chat_id=chat_id)


async def send_slack_if_configured(db, user_id: int, event: str, payload: dict) -> None:
    """Send to Slack if user has webhook URL configured."""
    from sqlalchemy import select
    from app.models.setting import Setting

    r = await db.execute(
        select(Setting).where(
            Setting.user_id == user_id,
            Setting.key == "slack_webhook_url",
        )
    )
    s = r.scalar_one_or_none()
    url = (s.value or "").strip() if s else ""
    if not url or not url.startswith("https://hooks.slack.com/"):
        return
    try:
        text = f"*Dorvey*: `{event}`\n```{payload}```"
        async with httpx.AsyncClient() as client:
            await client.post(url, json={"text": text}, timeout=5.0)
    except Exception:
        pass


async def notify_webhooks(
    db,
    user_id: int,
    event: str,
    payload: dict[str, Any],
) -> None:
    """Find user webhooks for event and fire them."""
    from sqlalchemy import select
    from app.models.webhook import Webhook

    r = await db.execute(
        select(Webhook).where(
            Webhook.user_id == user_id,
            Webhook.is_active == True,
        )
    )
    webhooks = r.scalars().all()
    for wh in webhooks:
        events = wh.events or []
        if events and event not in events:
            continue
        data = {"event": event, **payload}
        asyncio.create_task(fire_webhook(wh.url, data))
    await send_telegram_if_configured(db, user_id, event, payload)
    await send_slack_if_configured(db, user_id, event, payload)
    await send_email_if_configured(db, user_id, event, payload)


async def send_email_if_configured(db, user_id: int, event: str, payload: dict) -> None:
    """Send email if user has email configured."""
    from sqlalchemy import select
    from app.models.setting import Setting
    from app.models.user import User
    from app.services.email_notify import send_email

    r = await db.execute(select(Setting).where(Setting.user_id == user_id, Setting.key == "email_notifications_enabled"))
    s = r.scalar_one_or_none()
    if not s or str(s.value or "").lower() != "true":
        return
    u_r = await db.execute(select(User.email).where(User.id == user_id))
    email = (u_r.scalar() or "").strip() if u_r else ""
    if not email or "@" not in email:
        return
    import asyncio
    body = f"Dorvey event: {event}\n\n{payload}"
    await asyncio.to_thread(send_email, email, f"Dorvey: {event}", body)
