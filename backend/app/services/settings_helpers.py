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


KEYWORD_PROVIDERS = ("dataforseo", "fetchserp", "google_ads")


async def get_user_keyword_provider(db: AsyncSession, user_id: int) -> str:
    """Get selected keyword suggestion provider. Default: dataforseo."""
    r = await db.execute(
        select(Setting).where(Setting.user_id == user_id, Setting.key == "keyword_provider")
    )
    s = r.scalar_one_or_none()
    val = (s.value or "").strip().lower() if s and s.value else ""
    return val if val in KEYWORD_PROVIDERS else "dataforseo"


async def get_user_google_ads_credentials(db: AsyncSession, user_id: int) -> dict | None:
    """Get Google Ads API credentials. Returns dict with developer_token, client_id, client_secret, refresh_token or None."""
    r = await db.execute(
        select(Setting).where(
            Setting.user_id == user_id,
            Setting.key.in_([
                "google_ads_developer_token",
                "google_ads_client_id",
                "google_ads_client_secret",
                "google_ads_refresh_token",
                "google_ads_customer_id",
            ]),
        )
    )
    rows = {s.key: (s.value or "").strip() for s in r.scalars().all()}
    dev = rows.get("google_ads_developer_token", "")
    cid = rows.get("google_ads_client_id", "")
    secret = rows.get("google_ads_client_secret", "")
    refresh = rows.get("google_ads_refresh_token", "")
    customer_id = rows.get("google_ads_customer_id", "") or None
    if not dev or not cid or not secret or not refresh:
        return None
    out: dict = {
        "developer_token": dev,
        "client_id": cid,
        "client_secret": secret,
        "refresh_token": refresh,
    }
    if customer_id:
        out["customer_id"] = customer_id
    return out


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


async def get_keyword_provider_credentials(db: AsyncSession, user_id: int) -> tuple[str, dict] | None:
    """Get credentials for the selected keyword provider. Returns (provider, creds) or None.
    creds: for dataforseo {"login": str, "password": str}, for fetchserp {"api_key": str}.
    """
    provider = await get_user_keyword_provider(db, user_id)
    if provider == "dataforseo":
        creds = await get_user_dataforseo_credentials(db, user_id)
        if not creds:
            return None
        return ("dataforseo", {"login": creds[0], "password": creds[1]})
    if provider == "fetchserp":
        r = await db.execute(
            select(Setting).where(Setting.user_id == user_id, Setting.key == "fetchserp_api_key")
        )
        s = r.scalar_one_or_none()
        api_key = (s.value or "").strip() if s and s.value else ""
        if not api_key:
            return None
        return ("fetchserp", {"api_key": api_key})
    if provider == "google_ads":
        creds = await get_user_google_ads_credentials(db, user_id)
        if not creds:
            return None
        return ("google_ads", creds)
    return None
