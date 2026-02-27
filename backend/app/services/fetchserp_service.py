"""FetchSERP API service for keyword suggestions and volume."""

import httpx

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


async def fetch_keywords_for_keywords(
    api_key: str,
    *,
    seed: str,
    country: str = "US",
    limit: int = 100,
) -> list[dict]:
    """
    Fetch keyword suggestions from FetchSERP keywords_suggestions API.
    Returns list of dicts: {keyword, volume, cpc}.
    """
    if not (api_key or "").strip():
        return []
    seed_clean = (seed or "").strip()[:200]
    if not seed_clean:
        return []
    cc = _country_code(country)
    url = "https://www.fetchserp.com/api/v1/keywords_suggestions"
    # По доке: keywords — массив строк; передаём как keywords=seed
    params = [("keywords", seed_clean), ("country", cc)]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(
            url,
            params=params,
            headers={
                "Authorization": f"Bearer {api_key.strip()}",
                "Accept": "application/json",
            },
        )
    if r.status_code != 200:
        return []
    data = r.json()
    # По доке: ответ { "data": { "keywords_suggestions": [ { "keyword", "avg_monthly_searches", ... } ] } }
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}
    raw_list = (
        inner.get("keywords_suggestions")
        or data.get("keyword_suggestions")
        or data.get("keywords")
        or data.get("data")
        or (data if isinstance(data, list) else [])
    )
    if not isinstance(raw_list, list):
        raw_list = []
    out: list[dict] = []
    seen: set[str] = set()
    for item in raw_list[:limit]:
        if isinstance(item, str):
            kw = item.strip()
            vol, cpc = 0, 0.0
        else:
            kw = (item.get("keyword") or item.get("key") or item.get("query") or "").strip()
            vol = item.get("search_volume") or item.get("volume") or item.get("search_volume_avg") or item.get("avg_monthly_searches") or 0
            cpc = item.get("cpc") or item.get("avg_cpc") or 0.0
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
    return out


async def validate_fetchserp_api_key(api_key: str) -> tuple[bool, str]:
    """
    Validate FetchSERP API key by making a minimal request.
    Returns (ok, message).
    """
    key = (api_key or "").strip()
    if not key:
        return False, "Укажите API ключ"
    url = "https://www.fetchserp.com/api/v1/keywords_suggestions"
    # По доке FetchSERP: keywords — массив строк (GET ?keywords=test&country=us)
    params = [("keywords", "test"), ("country", "us")]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                url,
                params=params,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Accept": "application/json",
                },
            )
        if r.status_code == 200:
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
            return False, f"Сервис FetchSERP вернул ошибку (HTTP {r.status_code}). Скопируйте ключ заново из fetchserp.com/app (без пробелов) и нажмите «Проверить» снова. Если не поможет — попробуйте позже."
        return False, f"FetchSERP (HTTP {r.status_code}): {err}"
    except Exception as e:
        msg = str(e).lower()
        if "401" in msg or "auth" in msg or "invalid" in msg:
            return False, "Неверный или недействительный ключ"
        return False, str(e)[:150]
