"""Helpers to fetch user settings from DB."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import Setting


async def get_user_openai_key(db: AsyncSession, user_id: int) -> str | None:
    """Get OpenAI API key from user's integrations settings."""
    r = await db.execute(
        select(Setting).where(Setting.user_id == user_id, Setting.key == "openai_api_key")
    )
    s = r.scalar_one_or_none()
    if not s or not s.value or not s.value.strip():
        return None
    return s.value.strip()


async def get_user_dataforseo_credentials(db: AsyncSession, user_id: int) -> tuple[str, str] | None:
    """Get DataForSeo login and password from user's integrations. Returns (login, password) or None."""
    r = await db.execute(
        select(Setting).where(
            Setting.user_id == user_id,
            Setting.key.in_(["dataforseo_login", "dataforseo_password"]),
        )
    )
    rows = {s.key: (s.value or "").strip() for s in r.scalars().all()}
    login = rows.get("dataforseo_login", "")
    password = rows.get("dataforseo_password", "")
    if not login or not password:
        return None
    return (login, password)
