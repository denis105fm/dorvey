"""FetchSERP API service for keyword suggestions and volume."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# API base URL по спецификации — https://www.fetchserp.com. api.fetchserp.com не резолвится (Name or service not known).
FETCHSERP_API_BASE = os.getenv("FETCHSERP_API_BASE", "https://www.fetchserp.com").rstrip("/")
# Спека: Authorization: bearer <token> (lowercase). Часть прокси/Rails ожидает строго bearer.
_AUTH_HEADER = "bearer"

# ISO country code (uppercase) -> FetchSERP country (lowercase, as in their API)
COUNTRY_TO_FETCHSERP: dict[str, str] = {
    "RU": "ru", "US": "us", "KZ": "kz", "BY": "by", "UA": "ua",
    "DE": "de", "FR": "fr", "GB": "gb", "PL": "pl", "IT": "it",
    "ES": "es", "TR": "tr", "IN": "in", "BR": "br", "MX": "mx",
    "AR": "ar", "CO": "co", "ID": "id", "VN": "vn", "TH": "th",
    "PH": "ph", "EG": "eg", "ZA": "za", "NG": "ng", "KE": "ke",
    "CA": "ca", "AU": "au", "NL": "nl", "CH": "ch",
}


def _country_code(country: str) -> str:
    c = (country or "us").strip().upper()[:2]
    return COUNTRY_TO_FETCHSERP.get(c, "us")


def _clean_api_key(raw: str) -> str:
    """Убираем пробелы и невидимые символы при вставке из буфера."""
    if not raw:
        return ""
    s = raw.strip()
    return "".join(c for c in s if ord(c) >= 32 and ord(c) != 127 and c not in "\n\r\t")


async def fetch_keywords_for_keywords(
    api_key: str,
    *,
    seed: str,
    country: str = "US",
    limit: int = 100,
) -> tuple[list[dict], dict | None]:
    """
    Fetch keyword suggestions from FetchSERP keywords_suggestions API.
    Returns (list of dicts: {keyword, volume, cpc}, debug_info or None).
    debug_info is set when result is empty (to diagnose 0 keys).
    """
    if not (api_key or "").strip():
        return [], None
    key_clean = _clean_api_key(api_key) or (api_key or "").strip()
    if not key_clean:
        return [], None
    seed_clean = (seed or "").strip()[:200]
    if not seed_clean:
        return [], None
    cc = _country_code(country)  # всегда lowercase (us, ru), т.к. API требует
    url = f"{FETCHSERP_API_BASE}/api/v1/keywords_suggestions"
    # Пробуем оба формата: keywords[] (Rails) и keywords (как в их cURL в доке) — при 500 делаем retry.
    seed_parts = [s.strip() for s in seed_clean.split(",") if (s or "").strip() and len((s or "").strip()) >= 2]
    if not seed_parts:
        seed_parts = [seed_clean.strip()] if len(seed_clean.strip()) >= 2 else []
    # Не шлём запрос без валидных keywords — некоторые API на пустом вводе отдают 500
    keywords_param = [(kw.strip()) for kw in seed_parts[:10] if (kw or "").strip()]
    if not keywords_param:
        return [], None

    def make_params(param_key: str, kws: list[str]) -> list[tuple[str, str]]:
        """param_key: 'keywords' или 'keywords[]' (Rails vs их cURL в доке)."""
        p = [("country", cc)]
        for kw in kws:
            p.append((param_key, kw))
        return p

    headers = {
        "Authorization": f"{_AUTH_HEADER} {key_clean}",
        "Accept": "application/json",
        "User-Agent": "Dorvey/1.0 (+https://github.com/denis105fm/dorvey)",
    }
    r = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1) Сначала пробуем keywords[] (Rails-массив)
        params = make_params("keywords[]", keywords_param)
        r = await client.get(url, params=params, headers=headers)
        # 2) При 500 пробуем keywords без скобок (как в их доке cURL)
        if r.status_code == 500:
            params = make_params("keywords", keywords_param)
            r = await client.get(url, params=params, headers=headers)
        # 3) Всё ещё 500 и несколько фраз — пробуем одну фразу (keywords[])
        if r.status_code == 500 and len(keywords_param) > 1:
            params_one = make_params("keywords[]", keywords_param[:1])
            r = await client.get(url, params=params_one, headers=headers)
        # 4) Всё ещё 500 — одна фраза с keywords (без скобок)
        if r.status_code == 500:
            params_one = make_params("keywords", keywords_param[:1])
            r = await client.get(url, params=params_one, headers=headers)
    if r.status_code != 200:
        # Логируем заголовки ответа (cf-ray, x-request-id и т.д.) для отладки WAF/Cloudflare
        resp_headers = dict(r.headers) if r.headers else {}
        logger.warning(
            "FetchSERP keywords_suggestions: HTTP %s, url=%s body=%s response_headers=%s",
            r.status_code, r.url, (r.text or "")[:400], resp_headers,
        )
        err_msg = None
        try:
            j = r.json()
            err_msg = j.get("error") or j.get("message") or (j.get("data") if isinstance(j.get("data"), str) else None)
        except Exception:
            pass
        debug = {
            "request_url": str(r.url),
            "http_status": r.status_code,
            "response_preview": (r.text or "")[:500],
            "api_error": err_msg,
            "response_headers": dict(r.headers) if r.headers else None,
        }
        return [], debug
    data = r.json()
    # Парсим оба формата: data.keywords_suggestions (офиц. док) и топ-уровень keywords_suggestions (публичные примеры)
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}
    raw_list = (
        inner.get("keywords_suggestions")
        or inner.get("keywords")
        or (inner.get("data") if isinstance(inner.get("data"), list) else None)
        or data.get("keywords_suggestions")
        or data.get("keyword_suggestions")
        or data.get("keywords")
        or (data.get("data") if isinstance(data.get("data"), list) else None)
        or (data if isinstance(data, list) else [])
    )
    if not isinstance(raw_list, list):
        raw_list = []
    if not raw_list:
        logger.info(
            "FetchSERP keywords_suggestions: 0 keys, request_url=%s response_keys=%s body_preview=%s",
            r.url, list(data.keys()) if isinstance(data, dict) else type(data).__name__, (r.text or "")[:350],
        )
        debug = {
            "request_url": str(r.url),
            "response_keys": list(data.keys()) if isinstance(data, dict) else None,
            "response_preview": (r.text or "")[:500],
        }
    else:
        debug = None
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw_list[:limit]:
        if isinstance(item, str):
            kw = item.strip()
            vol, cpc = 0, 0.0
        else:
            kw = (item.get("keyword") or item.get("key") or item.get("query") or "").strip()
            vol = item.get("search_volume") or item.get("volume") or item.get("search_volume_avg") or item.get("avg_monthly_searches") or 0
            # Дока: low_top_of_page_bid_micros / high_top_of_page_bid_micros (микро-единицы)
            bid_lo = item.get("low_top_of_page_bid_micros")
            bid_hi = item.get("high_top_of_page_bid_micros")
            cpc = item.get("cpc") or item.get("avg_cpc") or 0.0
            if cpc == 0.0 and (bid_lo is not None or bid_hi is not None):
                try:
                    cpc = (float(bid_lo or 0) + float(bid_hi or 0)) / 2 / 1_000_000
                except (TypeError, ValueError):
                    pass
        if not kw or kw.lower() in seen:
            continue
        seen.add(kw.lower())
        try:
            vol = int(vol)
        except (TypeError, ValueError):
            vol = 0
        try:
            cpc = float(cpc)
        except (TypeError, ValueError):
            cpc = 0.0
        out.append({"keyword": kw, "volume": vol, "cpc": cpc})
    return out, debug


async def validate_fetchserp_api_key(api_key: str) -> tuple[bool, str]:
    """
    Проверка ключа через лёгкий эндпоинт GET /api/v1/user (без параметров).
    Возвращает (ok, message). Не тратит кредиты на keywords_suggestions.
    """
    key = _clean_api_key(api_key or "")
    if not key:
        return False, "Укажите API ключ"
    # Лёгкий пинг: только Bearer, без параметров — проверяет ключ и доступ к API
    url = f"{FETCHSERP_API_BASE}/api/v1/user"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                url,
                headers={
                    "Authorization": f"{_AUTH_HEADER} {key}",
                    "Accept": "application/json",
                    "User-Agent": "Dorvey/1.0 (+https://github.com/denis105fm/dorvey)",
                },
            )
        if r.status_code == 200:
            try:
                data = r.json()
                inner = data.get("data") or {}
                user = inner.get("user") or {}
                credits = user.get("api_credit")
                if credits is not None:
                    return True, f"Ключ действителен, подключение успешно. Кредитов: {credits}"
            except Exception:
                pass
            return True, "Ключ действителен, подключение успешно"
        if r.status_code in (401, 403):
            return False, "Неверный или недействительный ключ"
        body = r.text[:200] if r.text else ""
        try:
            data = r.json()
            err = data.get("error") or data.get("message") or body
        except Exception:
            err = body or f"HTTP {r.status_code}"
        err = (err or f"Ошибка {r.status_code}").strip()
        if r.status_code >= 500 or (err and err.lower() in ("internal server error", "internal server error.")):
            return False, f"Сервис FetchSERP вернул ошибку (HTTP {r.status_code}). Если ключ скопирован из fetchserp.com/app — возможно, запросы с нашего сервера блокируются; напишите в support@fetchserp.com."
        return False, f"FetchSERP (HTTP {r.status_code}): {err}"
    except Exception as e:
        msg = str(e).lower()
        if "401" in msg or "auth" in msg or "invalid" in msg:
            return False, "Неверный или недействительный ключ"
        return False, str(e)[:150]
