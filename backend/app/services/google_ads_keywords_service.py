"""Google Ads API (Keyword Plan Idea Service) for keyword suggestions and search volume.

Подсказки ключей и объём поиска через Google Ads API.
Требуется: Developer Token, OAuth (client_id, client_secret, refresh_token).
Документация: https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas
"""

import asyncio
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


def _create_test_client_sync(
    developer_token: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    manager_customer_id: str,
) -> tuple[str | None, str]:
    """
    Создаёт тестовый клиентский аккаунт под указанным тестовым MCC через CustomerService.createCustomerClient.
    manager_customer_id — ID тестового менеджера (MCC), без дефисов.
    Возвращает (customer_id нового аккаунта без префикса, или None, error_message).
    Документация: https://developers.google.com/google-ads/api/docs/account-management/create-account
    """
    from datetime import datetime

    try:
        from google.ads.googleads.client import GoogleAdsClient
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:
        return None, "Установите библиотеку google-ads: pip install google-ads"

    manager_id = _normalize_customer_id(manager_customer_id)
    if not manager_id:
        return None, "Укажите ID тестового менеджера (MCC)."

    config: dict[str, Any] = {
        "developer_token": developer_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "use_proto_plus": True,
        "login_customer_id": manager_id,
    }
    try:
        client = GoogleAdsClient.load_from_dict(config, version="v23")
    except Exception as e:
        return None, f"Ошибка инициализации клиента: {str(e)[:200]}"

    customer_service = client.get_service("CustomerService")
    customer = client.get_type("Customer")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    customer.descriptive_name = f"Test account (Dorvey) {now}"
    customer.currency_code = "USD"
    customer.time_zone = "America/New_York"

    try:
        response = customer_service.create_customer_client(
            customer_id=manager_id,
            customer_client=customer,
        )
    except GoogleAdsException as ex:
        err_msg = str(ex)
        if hasattr(ex, "failure") and ex.failure and hasattr(ex.failure, "errors"):
            parts = [err_msg]
            for err in ex.failure.errors:
                parts.append(getattr(err, "message", str(err)) or "")
            err_msg = " ".join(parts)[:400]
        if "PERMISSION_DENIED" in err_msg.upper() or "does not have permission" in err_msg:
            return None, (
                "Нет прав на создание аккаунта. Убедитесь, что в поле Customer ID указан именно "
                "тестовый менеджер (MCC), созданный по ссылке «Создать тестовый MCC», и что OAuth выполнен "
                "тем же Google-аккаунтом, который владеет этим тестовым MCC. Developer Token должен быть в режиме Test."
            )
        return None, err_msg or "Ошибка Google Ads API"
    except Exception as e:
        err_str = str(e)[:300]
        if "PERMISSION_DENIED" in err_str.upper() or "does not have permission" in err_str.lower():
            return None, (
                "Нет прав на создание аккаунта. Убедитесь, что в поле Customer ID указан именно "
                "тестовый менеджер (MCC), созданный по ссылке «Создать тестовый MCC», и что OAuth выполнен "
                "тем же Google-аккаунтом, который владеет этим тестовым MCC. Developer Token должен быть в режиме Test."
            )
        return None, err_str

    resource_name = getattr(response, "resource_name", None) or ""
    if resource_name.startswith("customers/"):
        new_customer_id = resource_name.replace("customers/", "").strip()
        return new_customer_id, ""
    return None, "Не удалось получить ID созданного аккаунта."


async def create_google_ads_test_client(
    creds: dict,
    manager_customer_id: str,
) -> tuple[str | None, str]:
    """
    Асинхронная обёртка: создаёт тестовый клиент под тестовым MCC.
    creds: developer_token, client_id, client_secret, refresh_token.
    Возвращает (customer_id нового аккаунта, error_message).
    """
    dev = (creds.get("developer_token") or "").strip()
    cid = (creds.get("client_id") or "").strip()
    secret = (creds.get("client_secret") or "").strip()
    refresh = (creds.get("refresh_token") or "").strip()
    if not dev or not cid or not secret or not refresh:
        return None, "Заполните Developer Token и OAuth в настройках Google Ads."

    new_id, err = await asyncio.to_thread(
        _create_test_client_sync,
        dev,
        cid,
        secret,
        refresh,
        manager_customer_id,
    )
    return new_id, err


def _fetch_keywords_via_official_client(
    developer_token: str,
    client_id: str,
    client_secret: str,
    refresh_token: str,
    customer_id: str,
    seed: str,
    country: str,
    limit: int,
    login_customer_id: str | None = None,
) -> tuple[list[dict], dict[str, Any] | None]:
    """
    Синхронный вызов через официальную библиотеку google-ads.
    login_customer_id — ID MCC (менеджера), обязателен для тестового Developer Token при запросах к дочернему аккаунту.
    Возвращает (list of {keyword, volume, cpc}, debug или None).
    """
    from google.ads.googleads.client import GoogleAdsClient

    config: dict[str, Any] = {
        "developer_token": developer_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "use_proto_plus": True,
    }
    if login_customer_id:
        config["login_customer_id"] = _normalize_customer_id(login_customer_id)
    use_customer_id = _normalize_customer_id(customer_id) or ""
    if not use_customer_id:
        raise ValueError("customer_id required for official client")

    # Явная версия API: v17 даёт 501 GRPC; библиотека 29.x поддерживает v23
    client = GoogleAdsClient.load_from_dict(config, version="v23")
    geo_id = _country_to_geo_id(country)
    keywords_seed = [s.strip() for s in seed.split(",") if (s or "").strip()][:10]
    if not keywords_seed:
        keywords_seed = [seed.strip()]

    keyword_plan_service = client.get_service("KeywordPlanIdeaService")
    google_ads_service = client.get_service("GoogleAdsService")
    geo_service = client.get_service("GeoTargetConstantService")
    language_rn = google_ads_service.language_constant_path("1000")
    geo_rn = geo_service.geo_target_constant_path(str(geo_id))

    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = use_customer_id
    request.language = language_rn
    request.geo_target_constants.append(geo_rn)
    request.keyword_plan_network = client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH
    request.include_adult_keywords = False
    request.keyword_seed.keywords.extend(keywords_seed)

    response = keyword_plan_service.generate_keyword_ideas(request=request)
    out: list[dict] = []
    seen: set[str] = set()
    for idea in response:
        text = (idea.text or "").strip()
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        metrics = idea.keyword_idea_metrics
        vol = int(metrics.avg_monthly_searches) if metrics else 0
        low = getattr(metrics, "low_top_of_page_bid_micros", None) or 0
        high = getattr(metrics, "high_top_of_page_bid_micros", None) or 0
        cpc = (int(low) + int(high)) / 2 / 1_000_000
        out.append({"keyword": text, "volume": vol, "cpc": round(cpc, 4)})
        if len(out) >= limit:
            break
    return out, None if out else {"message": "Google Ads не вернул идей по запросу."}


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
    manager_customer_id: str | None = None,
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
        msg = token_err or "Не удалось получить access_token"
        err_lower = (msg or "").strip().lower()
        if "bad request" in err_lower or "invalid_grant" in err_lower or "invalid request" in err_lower:
            msg = "Refresh Token не подходит к текущему Client ID. Если вы недавно исправили Client ID в настройках, нажмите «Получить refresh token» заново (войдите в Google) и сохраните настройки — затем снова подтяните ключи."
        return [], {"message": msg}

    # Customer ID: из параметра (настройки) или первый из listAccessibleCustomers
    use_customer_id = _normalize_customer_id(customer_id) if customer_id else None
    if not use_customer_id:
        customer_ids, list_debug = await _list_accessible_customers(access_token, dev)
        if list_debug:
            return [], list_debug
        use_customer_id = customer_ids[0] if customer_ids else None
    if not use_customer_id:
        return [], {"message": "Нет доступного рекламного аккаунта Google Ads."}

    # Для тестового токена при запросе к конкретному customer_id обязательно нужен MCC, иначе API вернёт PERMISSION_DENIED
    login_id = _normalize_customer_id(manager_customer_id) if manager_customer_id else None
    if use_customer_id and not login_id:
        return [], {
            "message": "Для подсказки ключей по выбранному аккаунту нужен Manager account ID (MCC). Заполните поле «Manager account ID (MCC)» в Настройках (например 185-780-6498), нажмите сохранение или «Проверить», затем снова подтяните ключи.",
        }

    # Сначала пробуем официальную библиотеку google-ads (корректный формат запроса)
    try:
        out, debug = await asyncio.to_thread(
            _fetch_keywords_via_official_client,
            dev,
            cid,
            secret,
            refresh,
            use_customer_id,
            seed_clean,
            country,
            min(limit, 100),
            login_id,
        )
        return out, debug
    except ImportError:
        logger.debug("google-ads library not available, using REST")
    except Exception as e:
        # Ошибки API Google — показываем пользователю, на REST не переходим (REST даёт 400)
        err_name = type(e).__name__
        if err_name == "GoogleAdsException":
            logger.warning("GoogleAdsException: %s", e)
            err_msg = str(e)
            details = []
            if hasattr(e, "failure") and e.failure and hasattr(e.failure, "errors"):
                for err in e.failure.errors:
                    details.append(getattr(err, "message", str(err)) or "")
                    loc = getattr(err, "location", None)
                    if loc:
                        path_elts = getattr(loc, "field_path_elements", None) or []
                        for fp in (path_elts or []):
                            details.append("  поле: " + str(getattr(fp, "field_name", fp)))
            # Короткая подсказка для типичных ошибок
            err_lower = err_msg.lower()
            details_str = " ".join(details).lower() if details else ""
            if "not yet enabled" in err_lower or "deactivated" in err_lower or "can't be accessed" in err_lower or "not yet enabled" in details_str or "deactivated" in details_str:
                return [], {
                    "message": "Рекламный аккаунт недоступен: ещё не активирован или деактивирован. Проверьте Customer ID в настройках (должен быть активный тестовый клиентский аккаунт под вашим MCC).",
                    "api_error": err_msg[:500],
                }
            is_perm_denied = (
                "permission_denied" in err_lower
                or "test accounts" in err_lower
                or "basic or standard access" in err_lower
                or ("developer token" in err_lower and "only approved" in err_lower)
                or "statuscode.permission_denied" in err_lower
                or "permission_denied" in details_str
                or "test accounts" in details_str
                or "only approved for use with test accounts" in err_lower
                or "only approved for use with test accounts" in details_str
            )
            if is_perm_denied:
                return [], {
                    "message": "Developer Token в режиме Test работает только с дочерними аккаунтами вашего MCC. Убедитесь: 1) В поле Manager account ID (MCC) указан ваш тестовый MCC (например 185-780-6498). 2) В поле Customer ID указан дочерний аккаунт из «Настройки дочерних аккаунтов» этого MCC (например 403-443-4560). Сохраните настройки и попробуйте снова."
                    + (" Если оба поля уже указаны верно: в Google Ads проверьте, что аккаунт из Customer ID отображается в «Настройки дочерних аккаунтов» вашего MCC и что вы получали Refresh Token под тем же Google-аккаунтом, у которого есть доступ к этому MCC и дочернему аккаунту." if login_id else ""),
                    "api_error": err_msg[:500],
                }
            msg = err_msg[:300]
            if details:
                msg += "\n" + "\n".join(details[:15])
            return [], {
                "message": msg,
                "api_error": err_msg[:500],
                "api_error_details": details[:20] if details else None,
            }
        # Любая другая ошибка официального клиента — возвращаем как есть, REST не вызываем
        err_str = str(e)
        err_lower = err_str.lower()
        if "not yet enabled" in err_lower or "deactivated" in err_lower or "can't be accessed" in err_lower:
            return [], {
                "message": "Рекламный аккаунт недоступен: ещё не активирован или деактивирован. Проверьте Customer ID в настройках (должен быть активный тестовый клиентский аккаунт под вашим MCC).",
                "api_error": err_str[:500],
            }
        is_permission_denied = (
            "permission_denied" in err_lower
            or "test accounts" in err_lower
            or "basic or standard access" in err_lower
            or ("developer token" in err_lower and "only approved" in err_lower)
            or "statuscode.permission_denied" in err_lower
            or "only approved for use with test accounts" in err_lower
        )
        if is_permission_denied:
            return [], {
                "message": "Developer Token в режиме Test работает только с дочерними аккаунтами вашего MCC. Убедитесь: 1) В поле Manager account ID (MCC) указан 185-780-6498. 2) В поле Customer ID указан именно дочерний аккаунт из раздела «Настройки дочерних аккаунтов» этого MCC (например 403-443-4560), а не другой аккаунт из переключателя (например 704-609-6309). Сохраните настройки и попробуйте снова."
                + (" Если оба поля уже указаны верно: в Google Ads проверьте, что дочерний аккаунт есть в «Настройки дочерних аккаунтов» MCC и что Refresh Token получен под тем же Google-аккаунтом, у которого есть доступ к MCC и дочернему." if login_id else ""),
                "api_error": err_str[:500],
            }
        return [], {
            "message": f"Ошибка Google Ads API: {err_name}: {err_str[:250]}",
            "api_error": err_str[:500],
        }

    # Fallback: REST API (только если библиотека google-ads не установлена)
    geo_id = _country_to_geo_id(country)
    geoTargetConstants = [f"geoTargetConstants/{geo_id}"]

    # POST generateKeywordIdeas
    url = f"{GOOGLE_ADS_BASE}/customers/{use_customer_id}:generateKeywordIdeas"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "developer-token": dev,
        "Content-Type": "application/json",
    }
    # login-customer-id: для тестового Developer Token обязателен MCC при запросе к дочернему аккаунту
    if manager_customer_id:
        mcc = _normalize_customer_id(manager_customer_id)
        if mcc:
            headers["login-customer-id"] = mcc
    elif customer_id:
        normalized_input = _normalize_customer_id(customer_id)
        if normalized_input and normalized_input != use_customer_id:
            headers["login-customer-id"] = normalized_input
    keywords_seed = [s.strip() for s in seed_clean.split(",") if (s or "").strip()][:10]
    if not keywords_seed:
        keywords_seed = [seed_clean]

    body: dict[str, Any] = {
        "keywordPlanNetwork": "GOOGLE_SEARCH",
        "includeAdultKeywords": False,
        "keywordSeed": {"keywords": keywords_seed},
        "geoTargetConstants": geoTargetConstants,
        "language": LANGUAGE_CONSTANT_EN,
    }
    # pageSize не передаём — убираем возможную причину 400

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
            "request_body_preview": str(body)[:400],
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
