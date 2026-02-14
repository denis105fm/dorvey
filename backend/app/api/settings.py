"""Settings API."""

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends
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
    "slack_webhook_url",
    "email_notifications_enabled",
]

BOOL_KEYS = {"ssl_auto_enabled", "exit_intent_enabled", "trust_elements_enabled", "email_notifications_enabled"}

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
    slack_webhook_url: Optional[str] = None


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
    for k in BOOL_KEYS:
        if k in out and isinstance(out.get(k), str):
            out[k] = str(out[k]).lower() == "true"
    return out


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
