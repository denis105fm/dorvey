"""DataForSeo API service for keyword volume by geo."""

import base64
import hashlib
import json

import httpx

CACHE_TTL_SEC = 86400

# ISO country code -> DataForSeo location_name (Google Ads)
COUNTRY_TO_LOCATION: dict[str, str] = {
    "RU": "Russia", "US": "United States", "KZ": "Kazakhstan", "BY": "Belarus",
    "UA": "Ukraine", "DE": "Germany", "FR": "France", "GB": "United Kingdom",
    "PL": "Poland", "IT": "Italy", "ES": "Spain", "TR": "Turkey", "IN": "India",
    "BR": "Brazil", "MX": "Mexico", "AR": "Argentina", "CO": "Colombia",
    "ID": "Indonesia", "VN": "Vietnam", "TH": "Thailand", "PH": "Philippines",
    "EG": "Egypt", "ZA": "South Africa", "NG": "Nigeria", "KE": "Kenya",
    "CA": "Canada", "AU": "Australia", "NL": "Netherlands", "CH": "Switzerland",
}

COUNTRY_TO_LANG: dict[str, str] = {
    "RU": "ru", "KZ": "ru", "BY": "ru", "UA": "uk",
    "US": "en", "GB": "en", "CA": "en", "AU": "en",
    "DE": "de", "FR": "fr", "ES": "es", "IT": "it",
    "PL": "pl", "TR": "tr", "BR": "pt", "MX": "es",
}


def get_location_name(country: str) -> str:
    c = (country or "").upper().strip()
    return COUNTRY_TO_LOCATION.get(c, "United States")


def get_language_code(country: str) -> str:
    c = (country or "").upper().strip()
    return COUNTRY_TO_LANG.get(c, "en")


def _cache_key(seed: str, country: str) -> str:
    h = hashlib.sha256(f"{seed}:{country}".encode()).hexdigest()[:16]
    return f"kw_dfseo:{h}"


async def _get_cache(key: str) -> list[dict] | None:
    try:
        import redis.asyncio as redis
        from app.core.config import settings
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        data = await r.get(key)
        await r.aclose()
        return json.loads(data) if data else None
    except Exception:
        return None


async def _set_cache(key: str, value: list[dict]) -> None:
    try:
        import redis.asyncio as redis
        from app.core.config import settings
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.setex(key, CACHE_TTL_SEC, json.dumps(value))
        await r.aclose()
    except Exception:
        pass


async def fetch_keywords_for_keywords(
    login: str, password: str, *, seed: str, country: str = "US",
    limit: int = 100, sort_by: str = "search_volume", use_cache: bool = True,
) -> list[dict]:
    if not login or not password:
        return []
    if use_cache:
        ck = _cache_key(seed.strip(), country)
        cached = await _get_cache(ck)
        if cached is not None:
            return cached[:limit]
    location = get_location_name(country)
    lang = get_language_code(country)
    auth = base64.b64encode(f"{login}:{password}".encode()).decode()
    url = "https://api.dataforseo.com/v3/keywords_data/google_ads/keywords_for_keywords/live"
    payload = [{
        "keywords": [seed.strip()[:80]],
        "location_name": location,
        "language_code": lang,
        "sort_by": sort_by,
        "include_adult_keywords": False,
    }]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=payload, headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
        })
    if r.status_code != 200:
        return []
    data = r.json()
    if data.get("status_code") != 20000:
        return []
    tasks = data.get("tasks") or []
    results = tasks[0].get("result") or [] if tasks else []
    out: list[dict] = []
    seen: set[str] = set()
    for item in results[:limit]:
        kw = (item.get("keyword") or "").strip()
        if not kw or kw.lower() in seen:
            continue
        seen.add(kw.lower())
        vol = item.get("search_volume") or 0
        cpc = item.get("cpc") or 0.0
        out.append({"keyword": kw, "volume": int(vol), "cpc": float(cpc)})
    if use_cache and out:
        await _set_cache(_cache_key(seed.strip(), country), out)
    return out
