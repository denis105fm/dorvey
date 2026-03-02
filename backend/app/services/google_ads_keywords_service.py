"""Google Ads API (Keyword Plan Idea Service) for keyword suggestions and search volume.

Подсказки ключей и объём поиска через Google Ads API.
Требуется: Developer Token, OAuth (client_id, client_secret, refresh_token).
Документация: https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# REST API version (Google Ads); v19 = generateKeywordIdeas REST reference
GOOGLE_ADS_API_VERSION = "v19"
GOOGLE_ADS_BASE = f"https://googleads.googleapis.com/{GOOGLE_ADS_API_VERSION}"

# ISO country code (uppercase) -> Google Ads geo target constant criterion_id (country-level).
# Resource name: geoTargetConstants/{id}. Source: Google Ads geo targets reference.
COUNTRY_TO_GEO_TARGET: dict[str, int] = {
    "US": 2840, "RU": 2643, "GB": 2826, "DE": 2276, "FR": 2250,
    "CA": 2124, "AU": 2036, "NL": 2045, "PL": 2614, "TR": 2632,
    "BR": 2076, "IN": 2343, "ES": 2724, "IT": 2380, "KZ": 2320,
    "UA": 2640, "BY": 2108, "MX": 2392, "AR": 2002, "CO": 2152,
    "ID": 2362, "VN": 2642, "TH": 2630, "PH": 2594, "ZA": 2728,
    "EG": 2228, "NG": 2426, "KE": 2388, "CH": 2258, "JP": 2392,
}
DEFAULT_GEO_TARGET_ID = 2840  # US

# Language constant: 1000 = English (used when no country->language mapping).
LANGUAGE_CONSTANT_EN = "languageConstants/1000"


def _country_to_geo_id(country: str) -> int:
    c = (country or "us").strip().upper()[:2]
    return COUNTRY_TO_GEO_TARGET.get(c, DEFAULT_GEO_TARGET_ID)


async def _get_access_token(client_id: str, client_secret: str, refresh_token: str) -> tuple[str | None, str]:
    """Обмен refresh_token на access_token. Возвращает (access_token, error_message)."""
    if not client_id or not client_secret or not refresh_token:
        return None, "Заполните Client ID, Client Secret и Refresh Token."
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if r.status_code != 200:
            body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            err = body.get("error_description") or body.get("error") or r.text[:200]
            return None, err or f"HTTP {r.status_code}"
        data = r.json()
        token = data.get("access_token")
        if not token:
            return None, "Не получен access_token"
        return token, ""
    except Exception as e:
        return None, str(e)[:200]


async def validate_google_ads_credentials(creds: dict) -> tuple[bool, str]:
    """
    Проверка учётки: обмен refresh_token на access_token.
    creds: dict с ключами developer_token, client_id, client_secret, refresh_token.
    """
    cid = (creds.get("client_id") or "").strip()
    secret = (creds.get("client_secret") or "").strip()
    refresh = (creds.get("refresh_token") or "").strip()
    if not cid or not secret or not refresh:
        return False, "Заполните Client ID, Client Secret и Refresh Token и сохраните настройки."
    token, err = await _get_access_token(cid, secret, refresh)
    if err:
        if "invalid_grant" in err.lower() or "invalid" in err.lower() or "401" in err:
            return False, "Неверный или истёкший Refresh Token. Получите новый (кнопка «Получить refresh token»)."
        return False, err[:150]
    return True, "Подключение успешно. Учётные данные действительны."


def _normalize_customer_id(customer_id: str) -> str:
    """Убирает дефисы: 123-456-7890 -> 1234567890."""
    return (customer_id or "").replace("-", "").strip()


async def _list_accessible_customers(
    access_token: str,
    developer_token: str,
) -> tuple[list[str], dict[str, Any] | None]:
    """
    GET customers:listAccessibleCustomers. Возвращает (list of customer_id без префикса, debug или None).
    """
    url = f"{GOOGLE_ADS_BASE}/customers:listAccessibleCustomers"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "developer-token": developer_token,
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers=headers)
        if r.status_code != 200:
            err_body = {}
            try:
                if r.headers.get("content-type", "").startswith("application/json"):
                    err_body = r.json()
            except Exception:
                pass
            err = err_body.get("error") or {}
            err_msg = err.get("message") if isinstance(err, dict) else str(err)
            debug = {
                "request_url": url,
                "http_status": r.status_code,
                "response_preview": (r.text or "")[:500],
                "api_error": err_msg or r.text[:200],
            }
            return [], debug
        data = r.json()
        names = data.get("resourceNames") or []
        customer_ids = []
        for n in names:
            if isinstance(n, str) and n.startswith("customers/"):
                customer_ids.append(n.replace("customers/", "").strip())
        if not customer_ids:
            debug = {
                "request_url": url,
                "response_preview": (r.text or "")[:500],
                "message": "Нет доступных рекламных аккаунтов. Убедитесь, что у приложения есть доступ к аккаунту Google Ads.",
            }
            return [], debug
        return customer_ids, None
    except Exception as e:
        return [], {
            "request_url": url,
            "api_error": str(e)[:300],
        }


async def fetch_keywords_for_keywords(
    developer_token: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    *,
    seed: str,
    country: str = "US",
    limit: int = 100,
    customer_id: str | None = None,
) -> tuple[list[dict], dict[str, Any] | None]:
    """
    Получение идей ключевых слов через Google Ads API (GenerateKeywordIdeas).
    Возвращает (list of {keyword, volume, cpc}, debug_info или None).
    """
    dev = (developer_token or "").strip()
    cid = (client_id or "").strip()
    secret = (client_secret or "").strip()
    refresh = (refresh_token or "").strip()
    seed_clean = (seed or "").strip()[:500]
    if not dev or not cid or not secret or not refresh:
        return [], {"message": "Укажите Developer Token и OAuth в Настройках (Google Ads)."}
    if not seed_clean or len(seed_clean) < 2:
        return [], {"message": "Введите ключевую фразу для подсказок."}

    access_token, token_err = await _get_access_token(cid, secret, refresh)
    if not access_token:
        return [], {"message": token_err or "Не удалось получить access_token"}

    # Customer ID: из параметра (настройки) или первый из listAccessibleCustomers
    use_customer_id = _normalize_customer_id(customer_id) if customer_id else None
    if not use_customer_id:
        customer_ids, list_debug = await _list_accessible_customers(access_token, dev)
        if list_debug:
            return [], list_debug
        use_customer_id = customer_ids[0] if customer_ids else None
    if not use_customer_id:
        return [], {"message": "Нет доступного рекламного аккаунта Google Ads."}

    geo_id = _country_to_geo_id(country)
    geoTargetConstants = [f"geoTargetConstants/{geo_id}"]

    # POST generateKeywordIdeas
    url = f"{GOOGLE_ADS_BASE}/customers/{use_customer_id}:generateKeywordIdeas"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "developer-token": dev,
        "Content-Type": "application/json",
    }
    keywords_seed = [s.strip() for s in seed_clean.split(",") if (s or "").strip()][:10]
    if not keywords_seed:
        keywords_seed = [seed_clean]

    body: dict[str, Any] = {
        "keywordPlanNetwork": "GOOGLE_SEARCH_AND_PARTNERS",
        "includeAdultKeywords": False,
        "keywordSeed": {"keywords": keywords_seed},
        "geoTargetConstants": geoTargetConstants,
        "language": LANGUAGE_CONSTANT_EN,
        "pageSize": min(max(limit, 1), 1000),
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(url, json=body, headers=headers)
    except Exception as e:
        logger.exception("Google Ads generateKeywordIdeas request failed")
        return [], {
            "request_url": url,
            "api_error": str(e)[:300],
        }

    if r.status_code != 200:
        err_body = {}
        try:
            if r.headers.get("content-type", "").startswith("application/json"):
                err_body = r.json()
        except Exception:
            pass
        err_msg = err_body.get("error")
        if isinstance(err_msg, dict):
            err_msg = err_msg.get("message") or err_msg.get("status") or str(err_msg)
        else:
            err_msg = str(err_msg) if err_msg is not None else r.text[:300]
        # Google API often returns error.details[].field with the invalid field path
        details = err_body.get("error", {}).get("details") if isinstance(err_body.get("error"), dict) else []
        if isinstance(details, list) and details and isinstance(details[0], dict):
            field = details[0].get("field") or details[0].get("reason")
            if field:
                err_msg = f"{err_msg} (поле: {field})"
        debug = {
            "request_url": url,
            "http_status": r.status_code,
            "response_preview": (r.text or "")[:500],
            "api_error": err_msg,
        }
        return [], debug

    data = r.json()
    results = data.get("results") or data.get("keywordIdeas") or []
    if not isinstance(results, list):
        results = []

    out: list[dict] = []
    seen: set[str] = set()
    for item in results[:limit]:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or item.get("keyword") or item.get("keywordIdea") or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        metrics = item.get("keywordIdeaMetrics") or item.get("metrics") or item
        vol = metrics.get("avgMonthlySearches") or metrics.get("avg_monthly_searches") or metrics.get("volume") or 0
        try:
            vol = int(vol)
        except (TypeError, ValueError):
            vol = 0
        low_micros = metrics.get("lowTopOfPageBidMicros") or metrics.get("low_top_of_page_bid_micros")
        high_micros = metrics.get("highTopOfPageBidMicros") or metrics.get("high_top_of_page_bid_micros")
        cpc = 0.0
        if low_micros is not None or high_micros is not None:
            try:
                lo = int(low_micros or 0)
                hi = int(high_micros or 0)
                cpc = (lo + hi) / 2 / 1_000_000
            except (TypeError, ValueError):
                pass
        if cpc == 0.0:
            raw_cpc = metrics.get("cpc") or metrics.get("avgCpcMicros") or 0
            try:
                cpc = float(raw_cpc)
                if cpc >= 1_000_000:
                    cpc = cpc / 1_000_000
            except (TypeError, ValueError):
                pass
        out.append({"keyword": text, "volume": vol, "cpc": round(cpc, 4)})

    debug = None
    if not out:
        debug = {
            "request_url": url,
            "response_preview": (r.text or "")[:500],
            "message": "Google Ads не вернул идей по запросу. Попробуйте другую фразу или регион.",
        }
    return out, debug
