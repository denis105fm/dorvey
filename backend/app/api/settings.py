"""Settings API."""

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import CurrentUser
from app.core.database import get_db
from app.models.setting import Setting

router = APIRouter()

INTEGRATION_KEYS = [
    "openai_api_key",
    "telegram_bot_token", "telegram_chat_id",
    "gsc_client_id", "gsc_client_secret", "gsc_refresh_token",
    "bing_api_key",
    "ssl_auto_enabled",
    "voluum_api_key", "voluum_api_url",
    "binom_api_key", "binom_api_url",
    "hotjar_site_id", "clarity_project_id",
    "exit_intent_enabled",
    "trust_elements_enabled",
    "click_tracking_enabled",
    "api_base_url",
    "visitor_capture_enabled",
    "email_capture_enabled",
    "vapid_public_key",
    "vapid_private_key",
    "slack_webhook_url",
    "email_notifications_enabled",
    "facebook_pixel_id",
    "google_ads_id",
    "min_clicks_for_profit",
    "news_api_key",
    "gnews_api_key",
    "mediastack_api_key",
    "guardian_api_key",
    "external_data_enabled",
    "seasonality_data_url",
    "dataforseo_login",
    "dataforseo_password",
]

BOOL_KEYS = {"ssl_auto_enabled", "exit_intent_enabled", "trust_elements_enabled", "click_tracking_enabled", "visitor_capture_enabled", "email_capture_enabled", "email_notifications_enabled", "external_data_enabled"}

WHITELABEL_KEYS = ["whitelabel_brand_name", "whitelabel_logo_url", "whitelabel_primary_color", "whitelabel_favicon_url"]
STORAGE_KEYS = ["s3_endpoint_url", "s3_access_key", "s3_secret_key", "s3_bucket"]
BILLING_KEYS = ["billing_plan"]


class SettingValue(BaseModel):
    value: Optional[Any] = None


class IntegrationsSettings(BaseModel):
    openai_api_key: Optional[str] = None
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    gsc_client_id: Optional[str] = None
    gsc_client_secret: Optional[str] = None
    gsc_refresh_token: Optional[str] = None
    bing_api_key: Optional[str] = None
    ssl_auto_enabled: Optional[bool] = True
    voluum_api_key: Optional[str] = None
    voluum_api_url: Optional[str] = None
    binom_api_key: Optional[str] = None
    binom_api_url: Optional[str] = None
    hotjar_site_id: Optional[str] = None
    clarity_project_id: Optional[str] = None
    exit_intent_enabled: Optional[bool] = False
    trust_elements_enabled: Optional[bool] = False
    click_tracking_enabled: Optional[bool] = False
    api_base_url: Optional[str] = None
    visitor_capture_enabled: Optional[bool] = False
    email_capture_enabled: Optional[bool] = False
    vapid_public_key: Optional[str] = None
    vapid_private_key: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    email_notifications_enabled: Optional[bool] = False
    facebook_pixel_id: Optional[str] = None
    google_ads_id: Optional[str] = None
    min_clicks_for_profit: Optional[int] = None  # порог кликов для учёта в доле прибыльных (по умолчанию 20)
    news_api_key: Optional[str] = None
    gnews_api_key: Optional[str] = None
    mediastack_api_key: Optional[str] = None
    guardian_api_key: Optional[str] = None
    external_data_enabled: Optional[bool] = False
    seasonality_data_url: Optional[str] = None
    dataforseo_login: Optional[str] = None
    dataforseo_password: Optional[str] = None


@router.get("/integrations/all")
async def get_integrations(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Setting).where(Setting.user_id == current_user.id, Setting.key.in_(INTEGRATION_KEYS))
    )
    rows = r.scalars().all()
    out: dict = {}
    for s in rows:
        if s.key == "ssl_auto_enabled" and s.value in ("true", "false"):
            out[s.key] = s.value == "true"
        else:
            out[s.key] = s.value or None
    for k in INTEGRATION_KEYS:
        if k not in out:
            out[k] = None
    if "vapid_private_key" in out and out.get("vapid_private_key"):
        out["vapid_private_key"] = "***"  # Never expose private key to frontend
    for k in BOOL_KEYS:
        if k in out and isinstance(out.get(k), str):
            out[k] = str(out[k]).lower() == "true"
    if "min_clicks_for_profit" in out and out["min_clicks_for_profit"] is not None:
        try:
            out["min_clicks_for_profit"] = int(out["min_clicks_for_profit"])
        except (TypeError, ValueError):
            out["min_clicks_for_profit"] = 20
    elif "min_clicks_for_profit" in out:
        out["min_clicks_for_profit"] = 20
    return out


@router.post("/vapid/generate")
async def generate_vapid_keys(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Generate VAPID keys for Web Push and save to settings.
    Public key: base64url (for browser PushManager.subscribe).
    Private key: PEM (for pywebpush on server).
    """
    try:
        from py_vapid import Vapid
        from py_vapid.utils import b64urlencode
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        raise HTTPException(503, "py-vapid не установлен")
    v = Vapid()
    v.generate_keys()
    priv_pem = v.private_pem().decode("utf-8")
    pub_bytes = v.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    pub_b64url = b64urlencode(pub_bytes)
    if not pub_b64url or not priv_pem:
        raise HTTPException(500, "Ошибка генерации ключей")
    for key_name, val in [("vapid_public_key", pub_b64url), ("vapid_private_key", priv_pem)]:
        r = await db.execute(select(Setting).where(Setting.user_id == current_user.id, Setting.key == key_name))
        s = r.scalar_one_or_none()
        if s:
            s.value = val
        else:
            db.add(Setting(user_id=current_user.id, key=key_name, value=val))
    await db.commit()
    return {"status": "ok", "message": "VAPID ключи сгенерированы и сохранены"}


class TestExternalApiRequest(BaseModel):
    source: str  # newsapi, gnews, mediastack, guardian
    api_key: str
    country: str = "us"


@router.post("/test-external-api")
async def test_external_api(
    data: TestExternalApiRequest,
    current_user: CurrentUser,
):
    """Test external news API key. Returns ok/error and sample headlines count."""
    src = (data.source or "").lower().strip()
    key = (data.api_key or "").strip()
    country = (data.country or "us").lower()[:2]
    if not key:
        raise HTTPException(400, "Укажите API ключ")
    allowed = ("newsapi", "gnews", "mediastack", "guardian")
    if src not in allowed:
        raise HTTPException(400, f"Источник должен быть: {', '.join(allowed)}")

    from app.services.external_data_service import (
        fetch_news_api,
        fetch_gnews,
        fetch_mediastack,
        fetch_guardian,
    )
    result: dict = {"ok": False, "source": src, "message": ""}
    try:
        if src == "newsapi":
            p = await fetch_news_api(country, key)
        elif src == "gnews":
            p = await fetch_gnews(country, key)
        elif src == "mediastack":
            p = await fetch_mediastack(country, key)
        else:
            p = await fetch_guardian(key)
        if p.get("ok"):
            n = len(p.get("headlines") or [])
            result["ok"] = True
            result["message"] = f"OK, получено {n} заголовков"
            result["count"] = n
        else:
            result["message"] = p.get("error") or "Ошибка запроса"
    except Exception as e:
        result["message"] = str(e)[:200]
    return result


@router.put("/integrations/all")
async def set_integrations(
    data: IntegrationsSettings,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    d = data.model_dump(exclude_none=True)
    for key, val in d.items():
        if key not in INTEGRATION_KEYS:
            continue
        if key == "min_clicks_for_profit" and val is not None:
            v = str(int(val))
        else:
            v = json.dumps(val) if isinstance(val, bool) else (val or "")
        r = await db.execute(
            select(Setting).where(Setting.user_id == current_user.id, Setting.key == key)
        )
        s = r.scalar_one_or_none()
        if s:
            s.value = v
        else:
            db.add(Setting(user_id=current_user.id, key=key, value=v))
    await db.commit()
    return {"status": "ok"}


class WhiteLabelSettings(BaseModel):
    brand_name: Optional[str] = None
    logo_url: Optional[str] = None
    primary_color: Optional[str] = None
    favicon_url: Optional[str] = None


@router.get("/whitelabel", response_model=WhiteLabelSettings)
async def get_whitelabel(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """White-label branding for the platform."""
    r = await db.execute(
        select(Setting).where(
            Setting.user_id == current_user.id,
            Setting.key.in_(WHITELABEL_KEYS),
        )
    )
    out = WhiteLabelSettings()
    for s in r.scalars().all():
        if s.key == "whitelabel_brand_name":
            out.brand_name = s.value or None
        elif s.key == "whitelabel_logo_url":
            out.logo_url = s.value or None
        elif s.key == "whitelabel_primary_color":
            out.primary_color = s.value or None
        elif s.key == "whitelabel_favicon_url":
            out.favicon_url = s.value or None
    return out


@router.put("/whitelabel")
async def set_whitelabel(
    data: WhiteLabelSettings,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Save white-label branding."""
    mapping = {
        "whitelabel_brand_name": data.brand_name,
        "whitelabel_logo_url": data.logo_url,
        "whitelabel_primary_color": data.primary_color,
        "whitelabel_favicon_url": data.favicon_url,
    }
    for key, val in mapping.items():
        v = val or ""
        r = await db.execute(
            select(Setting).where(Setting.user_id == current_user.id, Setting.key == key)
        )
        s = r.scalar_one_or_none()
        if s:
            s.value = v
        else:
            db.add(Setting(user_id=current_user.id, key=key, value=v))
    await db.commit()
    return {"status": "ok"}


@router.get("/{key}")
async def get_setting(
    key: str,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    r = await db.execute(
        select(Setting).where(Setting.user_id == current_user.id, Setting.key == key)
    )
    s = r.scalar_one_or_none()
    if not s:
        return {"key": key, "value": None}
    import json
    try:
        v = json.loads(s.value) if s.value else None
    except Exception:
        v = s.value
    return {"key": key, "value": v}


@router.put("/{key}")
async def set_setting(
    key: str,
    data: SettingValue,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    import json
    val = data.value
    if val is not None and not isinstance(val, str):
        val = json.dumps(val)
    r = await db.execute(
        select(Setting).where(Setting.user_id == current_user.id, Setting.key == key)
    )
    s = r.scalar_one_or_none()
    if s:
        s.value = str(val) if val is not None else None
    else:
        s = Setting(user_id=current_user.id, key=key, value=str(val) if val is not None else None)
        db.add(s)
    await db.commit()
    return {"key": key, "value": data.value}
