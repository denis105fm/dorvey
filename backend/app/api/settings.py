"""Settings API."""

import json
import secrets
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlencode, urlparse, quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import httpx
from jose import JWTError, jwt

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.database import get_db
from app.models.setting import Setting

router = APIRouter()

GOOGLE_ADS_OAUTH_SCOPE = "https://www.googleapis.com/auth/adwords"

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
    "keyword_provider",
    "fetchserp_api_key",
    "google_ads_developer_token",
    "google_ads_client_id",
    "google_ads_client_secret",
    "google_ads_refresh_token",
    "google_ads_customer_id",
    "google_ads_manager_customer_id",
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
    keyword_provider: Optional[str] = None  # dataforseo | fetchserp | google_ads
    fetchserp_api_key: Optional[str] = None
    google_ads_developer_token: Optional[str] = None
    google_ads_client_id: Optional[str] = None
    google_ads_client_secret: Optional[str] = None
    google_ads_refresh_token: Optional[str] = None
    google_ads_customer_id: Optional[str] = None  # опционально: 123-456-7890 (если не задан — берётся первый из listAccessibleCustomers)
    google_ads_manager_customer_id: Optional[str] = None  # MCC, под которым дочерний аккаунт; нужен для тестового Developer Token


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
    source: str  # newsapi, gnews, mediastack, guardian, fetchserp, google_ads, ...
    api_key: Optional[str] = None  # не нужен для google_ads (берётся из настроек)
    country: str = "us"


class TestOpenAIRequest(BaseModel):
    api_key: str


@router.post("/test-openai")
async def test_openai_key(data: TestOpenAIRequest, current_user: CurrentUser):
    """Проверка OpenAI API ключа: один короткий запрос. Возвращает ok и сообщение."""
    key = (data.api_key or "").strip()
    if not key:
        raise HTTPException(400, "Укажите API ключ")
    from app.services.openai_service import openai_service
    result = {"ok": False, "message": ""}
    try:
        client = openai_service.get_client_for_key(key)
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
        )
        if resp.choices and resp.choices[0].message.content:
            result["ok"] = True
            result["message"] = "Ключ активен, AI доступен"
        else:
            result["message"] = "Пустой ответ от API"
    except Exception as e:
        err = str(e).lower()
        if "invalid" in err or "authentication" in err or "api_key" in err or "401" in err:
            result["message"] = "Неверный или недействительный ключ"
        elif "rate" in err or "429" in err:
            result["message"] = "Лимит запросов (ключ рабочий)"
        else:
            result["message"] = str(e)[:150]
    return result


@router.post("/test-external-api")
async def test_external_api(
    data: TestExternalApiRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """Test external news API key. Returns ok/error and sample headlines count."""
    src = (data.source or "").lower().strip()
    key = (data.api_key or "").strip()
    country = (data.country or "us").lower()[:2]
    allowed = ("newsapi", "gnews", "mediastack", "guardian", "fetchserp", "bing", "clarity", "hotjar", "google_ads")
    if src not in allowed:
        raise HTTPException(400, f"Источник должен быть: {', '.join(allowed)}")

    result: dict = {"ok": False, "source": src, "message": ""}

    if src == "google_ads":
        from app.services.settings_helpers import get_keyword_provider_credentials
        from app.services.google_ads_keywords_service import validate_google_ads_credentials
        creds = await get_keyword_provider_credentials(db, current_user.id)
        if not creds or creds[0] != "google_ads":
            result["message"] = "Выберите провайдер Google Ads и заполните Developer Token, Client ID, Client Secret и Refresh Token, затем сохраните."
            return result
        try:
            ok, message = await validate_google_ads_credentials(creds[1])
            result["ok"] = ok
            result["message"] = message or "Ошибка проверки"
        except Exception as e:
            result["ok"] = False
            result["message"] = (str(e)[:200]) or "Ошибка проверки"
        return result

    if not key:
        raise HTTPException(400, "Укажите API ключ")

    if src == "bing":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://ssl.bing.com/webmaster/api.svc/json/GetUserSites",
                    params={"apikey": key},
                )
            if r.status_code != 200:
                try:
                    body = r.json()
                    result["message"] = body.get("Message", body.get("message", r.text[:150]))
                except Exception:
                    result["message"] = r.text[:150] or f"HTTP {r.status_code}"
                return result
            data = r.json()
            sites = data.get("d") if isinstance(data.get("d"), list) else []
            result["ok"] = True
            result["message"] = f"OK, сайтов в аккаунте: {len(sites)}"
            result["count"] = len(sites)
        except Exception as e:
            result["ok"] = False
            result["message"] = (str(e)[:200]) or "Ошибка проверки ключа"
        return result

    if src == "clarity":
        try:
            # Clarity ID может содержать @ (например vo4y@wsy3s)
            cid = "".join(c for c in key if c.isalnum() or c in "-_@")
            if not cid:
                result["message"] = "Введите Project ID (из clarity.microsoft.com)"
                return result
            url_encoded_id = quote(cid, safe="")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0"}
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                r = await client.get(f"https://www.clarity.ms/tag/{url_encoded_id}", headers=headers)
            if r.status_code == 200 and (r.text or "").strip():
                result["ok"] = True
                result["message"] = "ID верный, скрипт Clarity доступен"
            elif r.status_code in (200, 204) and cid:
                # 204 или пустой ответ — сервер иногда не отдаёт скрипт на проверку; ID сохраняем
                result["ok"] = True
                result["message"] = "ID принят. После деплоя проверьте запись сессий в clarity.microsoft.com."
            elif r.status_code == 400 and "@" in cid:
                # Для ID с @ сервер может возвращать 400 при запросе с бэкенда; в браузере на сайте скрипт может грузиться
                result["ok"] = True
                result["message"] = "ID принят (проверка с сервера недоступна для этого формата). Сохраните и задеплойте — скрипт подставится в страницы."
            else:
                result["message"] = f"Скрипт не найден (HTTP {r.status_code}). Проверьте Project ID в Параметры → Обзор на clarity.microsoft.com."
        except Exception as e:
            result["ok"] = False
            result["message"] = (str(e)[:200]) or "Ошибка проверки"
        return result

    if src == "hotjar":
        try:
            key_alpha = "".join(c for c in key if c.isalnum() or c in "-_")
            if not key_alpha:
                result["message"] = "Введите Hotjar Site ID (число) или Contentsquare ID (например 785bcc77e264f)."
                return result
            if key_alpha.isdigit():
                # Классический Hotjar — числовой ID
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    r = await client.get(f"https://static.hotjar.com/c/hotjar-{key_alpha}.js?sv=6")
                if r.status_code == 200 and (r.text or "").strip():
                    result["ok"] = True
                    result["message"] = "ID верный, скрипт Hotjar доступен"
                else:
                    result["message"] = f"Скрипт не найден (HTTP {r.status_code}). Проверьте Site ID в hotjar.com."
            else:
                # Contentsquare (Hotjar evolved) — ID вида 785bcc77e264f (12 символов)
                # Сервер может отдавать 200 и для неверного ID — проверяем длину и содержание
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                    r = await client.get(f"https://t.contentsquare.net/uxa/{key_alpha}.js")
                body = (r.text or "").strip()
                if r.status_code == 200 and len(body) > 2000 and ("contentsquare" in body.lower() or "csq" in body.lower() or "uxa" in body.lower()):
                    result["ok"] = True
                    result["message"] = "ID верный, скрипт Contentsquare (Hotjar) доступен"
                else:
                    result["message"] = "Скрипт не найден или неверный ID. Убедитесь, что скопировали полный ID из app.contentsquare.com (например 785bcc77e264f)."
        except Exception as e:
            result["ok"] = False
            result["message"] = (str(e)[:200]) or "Ошибка проверки"
        return result

    if src == "fetchserp":
        try:
            from app.services.fetchserp_service import validate_fetchserp_api_key
            ok, message = await validate_fetchserp_api_key(key)
            result["ok"] = ok
            result["message"] = message or "Ошибка проверки ключа"
        except Exception as e:
            result["ok"] = False
            result["message"] = (str(e)[:200]) or "Ошибка проверки ключа"
        return result

    from app.services.external_data_service import (
        fetch_news_api,
        fetch_gnews,
        fetch_mediastack,
        fetch_guardian,
    )
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


class GoogleAdsOAuthStartRequest(BaseModel):
    client_id: str
    client_secret: str


@router.post("/google-ads-oauth-start")
async def google_ads_oauth_start(
    request: Request,
    data: GoogleAdsOAuthStartRequest,
    current_user: CurrentUser,
):
    """
    Начать OAuth для Google Ads: вернуть URL для перехода в Google.
    После авторизации callback сохранит refresh_token в настройки пользователя.
    """
    cid = (data.client_id or "").strip()
    secret = (data.client_secret or "").strip()
    if not cid or not secret:
        raise HTTPException(400, "Введите Client ID и Client Secret")
    base = _gsc_base_url(request)
    redirect_uri = f"{base}/api/settings/google-ads-oauth-callback"
    state = secrets.token_urlsafe(32)
    payload = {"user_id": current_user.id, "client_id": cid, "client_secret": secret}
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.setex(f"google_ads_oauth:{state}", 600, json.dumps(payload))
        await r.aclose()
    except Exception as e:
        raise HTTPException(503, f"Сервис временно недоступен ({e})")
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_ADS_OAUTH_SCOPE,
        "state": state,
        "access_type": "offline",
        "prompt": "select_account consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"url": url, "redirect_uri": redirect_uri}


@router.get("/google-ads-oauth-callback", response_class=HTMLResponse)
async def google_ads_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Callback после авторизации в Google: обмен code на refresh_token и сохранение.
    Возвращает HTML с postMessage для закрытия окна и обновления настроек.
    """
    base = _gsc_base_url(request)
    if error or not code or not state:
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
        <p>Ошибка авторизации. Закройте окно.</p>
        <script>try { if (window.opener) window.opener.postMessage({ type: "google_ads_refresh_error" }, "*"); } catch(e){} window.close();</script>
        </body></html>"""
        return HTMLResponse(html)
    try:
        import redis.asyncio as redis
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        raw = await r.get(f"google_ads_oauth:{state}")
        await r.delete(f"google_ads_oauth:{state}")
        await r.aclose()
    except Exception:
        raw = None
    if not raw:
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
        <p>Сессия истекла. Повторите «Получить refresh token».</p>
        <script>try { if (window.opener) window.opener.postMessage({ type: "google_ads_refresh_error" }, "*"); } catch(e){} window.close();</script>
        </body></html>"""
        return HTMLResponse(html)
    try:
        payload = json.loads(raw)
        user_id = int(payload.get("user_id", 0))
        cid = (payload.get("client_id") or "").strip()
        secret = (payload.get("client_secret") or "").strip()
    except (json.JSONDecodeError, ValueError, TypeError):
        user_id = 0
        cid = secret = ""
    if not user_id or not cid or not secret:
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
        <p>Ошибка данных. Закройте окно.</p>
        <script>try { if (window.opener) window.opener.postMessage({ type: "google_ads_refresh_error" }, "*"); } catch(e){} window.close();</script>
        </body></html>"""
        return HTMLResponse(html)
    redirect_uri = f"{base}/api/settings/google-ads-oauth-callback"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": cid,
                "client_secret": secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
    if resp.status_code != 200:
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
        <p>Не удалось обменять код на токен. Закройте окно и попробуйте снова.</p>
        <script>try { if (window.opener) window.opener.postMessage({ type: "google_ads_refresh_error" }, "*"); } catch(e){} window.close();</script>
        </body></html>"""
        return HTMLResponse(html)
    data = resp.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        html = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
        <p>Refresh token не получен. При авторизации выберите аккаунт и дайте доступ. Закройте окно и попробуйте снова.</p>
        <script>try { if (window.opener) window.opener.postMessage({ type: "google_ads_refresh_error" }, "*"); } catch(e){} window.close();</script>
        </body></html>"""
        return HTMLResponse(html)
    r = await db.execute(
        select(Setting).where(Setting.user_id == user_id, Setting.key == "google_ads_refresh_token")
    )
    s = r.scalar_one_or_none()
    if s:
        s.value = refresh_token
    else:
        db.add(Setting(user_id=user_id, key="google_ads_refresh_token", value=refresh_token))
    await db.commit()
    html = """<!DOCTYPE html><html><head><meta charset="utf-8"></head><body>
    <p>Refresh token сохранён. Можно закрыть окно.</p>
    <script>try { if (window.opener) window.opener.postMessage({ type: "google_ads_refresh_saved" }, "*"); } catch(e){} setTimeout(function() { window.close(); }, 1500);</script>
    </body></html>"""
    return HTMLResponse(html)


class CreateGoogleAdsTestAccountRequest(BaseModel):
    """ID тестового менеджера (MCC). Если не указан — используется Customer ID из настроек."""
    manager_customer_id: Optional[str] = None


@router.post("/google-ads-create-test-account")
async def google_ads_create_test_account(
    data: CreateGoogleAdsTestAccountRequest,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Создать тестовый клиентский аккаунт под тестовым MCC через API (CustomerService.createCustomerClient).
    Требуется: Developer Token в режиме Test, OAuth и ID тестового менеджера.
    Если manager_customer_id не передан — используется Customer ID из настроек как MCC.
    Документация: https://developers.google.com/google-ads/api/docs/best-practices/test-accounts
    """
    from app.services.settings_helpers import get_user_google_ads_credentials
    from app.services.google_ads_keywords_service import create_google_ads_test_client

    creds = await get_user_google_ads_credentials(db, current_user.id)
    if not creds:
        raise HTTPException(400, "Заполните Developer Token и OAuth в блоке Google Ads и сохраните настройки.")

    manager_id = (data.manager_customer_id or "").strip() or (creds.get("customer_id") or "").strip()
    if not manager_id:
        raise HTTPException(
            400,
            "Укажите ID тестового менеджера (MCC) в поле «Customer ID» и сохраните настройки, "
            "либо передайте manager_customer_id в теле запроса. "
            "Тестовый менеджер создаётся по ссылке: https://ads.google.com/nav/selectaccount?sf=mt",
        )

    new_customer_id, err = await create_google_ads_test_client(creds, manager_id)
    if err:
        raise HTTPException(400, err)
    # Формат с дефисами для подстановки в поле Customer ID
    formatted = f"{new_customer_id[:3]}-{new_customer_id[3:6]}-{new_customer_id[6:]}" if len(new_customer_id) >= 10 else new_customer_id
    return {"customer_id": new_customer_id, "customer_id_formatted": formatted}


GSC_SCOPE = "https://www.googleapis.com/auth/indexing"


def _gsc_base_url(request: Request) -> str:
    """Базовый URL для GSC OAuth: PUBLIC_APP_URL, иначе из заголовков прокси, иначе request.base_url.
    Для не-localhost всегда принудительно https (Google требует HTTPS для redirect_uri)."""
    base = (settings.PUBLIC_APP_URL or "").strip().rstrip("/")
    if not base:
        proto = request.headers.get("X-Forwarded-Proto", "").strip().lower()
        host = request.headers.get("X-Forwarded-Host", "").strip()
        if proto and host:
            base = f"{proto}://{host}"
        else:
            base = str(request.base_url).rstrip("/")
    base = base.rstrip("/")
    # Google OAuth требует HTTPS для redirect_uri (кроме localhost)
    if base.startswith("http://"):
        try:
            p = urlparse(base)
            if p.hostname and p.hostname not in ("localhost", "127.0.0.1"):
                base = "https://" + (p.netloc or "") + (p.path or "")
        except Exception:
            pass
    return base.rstrip("/") or base


@router.get("/gsc-oauth-start")
async def gsc_oauth_start(
    request: Request,
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """
    Начать OAuth для GSC: вернуть URL для редиректа в Google.
    Требует сохранённые gsc_client_id и gsc_client_secret у пользователя.
    """
    r = await db.execute(
        select(Setting).where(
            Setting.user_id == current_user.id,
            Setting.key.in_(["gsc_client_id", "gsc_client_secret"]),
        )
    )
    creds = {s.key: (s.value or "").strip() for s in r.scalars().all()}
    cid = creds.get("gsc_client_id")
    secret = creds.get("gsc_client_secret")
    if not cid or not secret:
        raise HTTPException(
            400,
            "Сначала сохраните Client ID и Client Secret в настройках и нажмите «Сохранить интеграции».",
        )
    base = _gsc_base_url(request)
    redirect_uri = f"{base}/api/settings/gsc-oauth-callback"
    state_payload = {
        "sub": str(current_user.id),
        "purpose": "gsc_oauth",
        "exp": datetime.utcnow() + timedelta(minutes=10),
    }
    state = jwt.encode(
        state_payload,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    params = {
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GSC_SCOPE,
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"redirect_url": url}


@router.get("/gsc-oauth-callback")
async def gsc_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Callback после авторизации в Google: обмен code на refresh_token и сохранение.
    Редирект на /settings?gsc_token=ok или ?gsc_token=error.
    """
    base = _gsc_base_url(request)
    frontend_settings = f"{base}/settings"
    if error:
        return RedirectResponse(url=f"{frontend_settings}?gsc_token=error&message={error}")
    if not code or not state:
        return RedirectResponse(url=f"{frontend_settings}?gsc_token=error&message=missing_code")
    try:
        payload = jwt.decode(
            state,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("purpose") != "gsc_oauth":
            return RedirectResponse(url=f"{frontend_settings}?gsc_token=error")
        user_id = int(payload.get("sub", 0))
    except (JWTError, ValueError):
        return RedirectResponse(url=f"{frontend_settings}?gsc_token=error")
    if not user_id:
        return RedirectResponse(url=f"{frontend_settings}?gsc_token=error")

    r = await db.execute(
        select(Setting).where(
            Setting.user_id == user_id,
            Setting.key.in_(["gsc_client_id", "gsc_client_secret"]),
        )
    )
    creds = {s.key: (s.value or "").strip() for s in r.scalars().all()}
    cid = creds.get("gsc_client_id")
    secret = creds.get("gsc_client_secret")
    if not cid or not secret:
        return RedirectResponse(url=f"{frontend_settings}?gsc_token=error&message=no_creds")

    redirect_uri = f"{base}/api/settings/gsc-oauth-callback"
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": cid,
                "client_secret": secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10.0,
        )
    if resp.status_code != 200:
        return RedirectResponse(url=f"{frontend_settings}?gsc_token=error&message=exchange_failed")
    data = resp.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return RedirectResponse(url=f"{frontend_settings}?gsc_token=error&message=no_refresh_token")

    r = await db.execute(
        select(Setting).where(Setting.user_id == user_id, Setting.key == "gsc_refresh_token")
    )
    s = r.scalar_one_or_none()
    if s:
        s.value = refresh_token
    else:
        db.add(Setting(user_id=user_id, key="gsc_refresh_token", value=refresh_token))
    await db.commit()
    return RedirectResponse(url=f"{frontend_settings}?gsc_token=ok")


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
