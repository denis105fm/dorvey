"""External data service: fetch from NewsAPI and other sources, normalize, cache."""

import time
from typing import Any, Optional

import httpx

# In-memory cache: key -> (payload, expiry_ts)
_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL_SEC = 3600  # 1 hour


def _cache_key(source: str, country: str, days: int) -> str:
    return f"{source}:{country}:{days}"


def _get_cached(key: str) -> Optional[dict]:
    if key not in _cache:
        return None
    payload, expiry = _cache[key]
    if time.time() > expiry:
        del _cache[key]
        return None
    return payload


def _set_cache(key: str, payload: dict) -> None:
    _cache[key] = (payload, time.time() + _CACHE_TTL_SEC)


async def fetch_news_api(country_code: str, api_key: str, page_size: int = 10) -> dict[str, Any]:
    """Fetch top headlines from NewsAPI for country. Returns normalized structure."""
    country = (country_code or "us").lower()[:2]
    url = "https://newsapi.org/v2/top-headlines"
    params = {"country": country, "pageSize": min(page_size, 100), "apiKey": api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return {"ok": False, "headlines": [], "sources_used": ["newsapi"], "error": "fetch_failed"}

    articles = data.get("articles") or []
    headlines = [
        {"title": a.get("title") or "", "source": (a.get("source") or {}).get("name"), "published_at": a.get("publishedAt")}
        for a in articles[:20]
    ]
    return {
        "ok": True,
        "headlines": headlines,
        "sources_used": ["newsapi"],
        "country": country,
    }


async def fetch_gnews(country_code: str, api_key: str, limit: int = 10) -> dict[str, Any]:
    """Fetch top headlines from GNews for country."""
    country = (country_code or "us").lower()[:2]
    url = "https://gnews.io/api/v4/top-headlines"
    params = {"country": country, "max": min(limit, 50), "apikey": api_key}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return {"ok": False, "headlines": [], "error": "fetch_failed"}
    articles = data.get("articles") or []
    headlines = [
        {"title": a.get("title") or "", "source": a.get("source", {}).get("name"), "published_at": a.get("publishedAt")}
        for a in articles[:20]
    ]
    return {"ok": True, "headlines": headlines, "country": country}


async def fetch_mediastack(country_code: str, api_key: str, limit: int = 10) -> dict[str, Any]:
    """Fetch news from Mediastack for country."""
    country = (country_code or "us").lower()[:2]
    url = "https://api.mediastack.com/v1/news"
    params = {"access_key": api_key, "countries": country, "limit": min(limit, 100)}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return {"ok": False, "headlines": [], "error": "fetch_failed"}
    data_list = data.get("data") if isinstance(data.get("data"), list) else []
    headlines = [
        {"title": a.get("title") or "", "source": a.get("source"), "published_at": a.get("published_at")}
        for a in data_list[:20]
    ]
    return {"ok": True, "headlines": headlines, "country": country}


async def fetch_guardian(api_key: str, limit: int = 10) -> dict[str, Any]:
    """Fetch from The Guardian (no country filter in free tier; general headlines)."""
    url = "https://content.guardianapis.com/search"
    params = {"api-key": api_key, "format": "json", "page-size": min(limit, 50)}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return {"ok": False, "headlines": [], "error": "fetch_failed"}
    resp = data.get("response") or {}
    results = resp.get("results") or []
    headlines = [
        {"title": a.get("webTitle") or "", "source": "Guardian", "published_at": a.get("webPublicationDate")}
        for a in results[:20]
    ]
    return {"ok": True, "headlines": headlines}


async def fetch_rest_countries(country_code: str) -> dict[str, Any]:
    """Fetch country metadata from REST Countries (free, no key). Returns name, languages, currencies, region."""
    country = (country_code or "us").lower()[:2]
    url = f"https://restcountries.com/v3.1/alpha/{country}"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return {"ok": False, "country": country, "error": "fetch_failed"}
    items = data if isinstance(data, list) else [data]
    if not items:
        return {"ok": False, "country": country}
    c = items[0]
    names = c.get("name") or {}
    return {
        "ok": True,
        "country": country,
        "name": names.get("common") or names.get("official") or country.upper(),
        "region": c.get("region"),
        "subregion": c.get("subregion"),
        "languages": list((c.get("languages") or {}).values())[:5],
        "currencies": list((c.get("currencies") or {}).keys()),
        "population": c.get("population"),
    }


async def get_external_signals(
    country_code: str,
    days: int = 7,
    news_api_key: Optional[str] = None,
    gnews_api_key: Optional[str] = None,
    mediastack_api_key: Optional[str] = None,
    guardian_api_key: Optional[str] = None,
    seasonality_data_url: Optional[str] = None,
) -> dict[str, Any]:
    """
    Aggregate external signals for a country and period.
    Returns normalized structure for use in profitability/recommendations.
    News: tries NewsAPI, then GNews, Mediastack, Guardian as fallbacks.
    """
    country = (country_code or "us").lower()[:2]
    out: dict[str, Any] = {
        "country": country,
        "period_days": days,
        "sources_used": [],
        "news": None,
        "seasonality": None,
        "country_info": None,
    }

    # News: try NewsAPI, GNews, Mediastack, Guardian
    news_key = (news_api_key or "").strip() or None
    gnews_key = (gnews_api_key or "").strip() or None
    mstack_key = (mediastack_api_key or "").strip() or None
    guard_key = (guardian_api_key or "").strip() or None
    any_news_key = news_key or gnews_key or mstack_key or guard_key

    if any_news_key:
        cache_key = _cache_key("news", country, days)
        cached = _get_cached(cache_key)
        if cached is not None:
            out["news"] = {k: v for k, v in cached.items() if k != "sources"}
            out["sources_used"] = list(set(out["sources_used"] + (cached.get("sources") or ["news"])))
        else:
            headlines: list[dict] = []
            used: list[str] = []
            if news_key:
                p = await fetch_news_api(country, news_key)
                if p.get("ok") and p.get("headlines"):
                    headlines = p["headlines"]
                    used.append("newsapi")
            if not headlines and gnews_key:
                p = await fetch_gnews(country, gnews_key)
                if p.get("ok") and p.get("headlines"):
                    headlines = p["headlines"]
                    used.append("gnews")
            if not headlines and mstack_key:
                p = await fetch_mediastack(country, mstack_key)
                if p.get("ok") and p.get("headlines"):
                    headlines = p["headlines"]
                    used.append("mediastack")
            if not headlines and guard_key:
                p = await fetch_guardian(guard_key)
                if p.get("ok") and p.get("headlines"):
                    headlines = p["headlines"]
                    used.append("guardian")
            news_data = {"headlines": headlines, "count": len(headlines), "sources": used}
            out["news"] = {"headlines": headlines, "count": len(headlines)}
            _set_cache(cache_key, news_data)
            out["sources_used"].extend(used)

    # Seasonality (optional URL): fetch JSON with coefficients by country/month
    if seasonality_data_url and (seasonality_data_url or "").strip():
        key = _cache_key("seasonality", country, days)
        cached = _get_cached(key)
        if cached is not None:
            out["seasonality"] = cached
            if "seasonality" not in out["sources_used"]:
                out["sources_used"].append("seasonality")
        else:
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    r = await client.get(seasonality_data_url.strip())
                    r.raise_for_status()
                    data = r.json()
                # Expect structure like { "country_code": { "month": coefficient } } or list
                if isinstance(data, dict) and country in data:
                    out["seasonality"] = data[country] if isinstance(data[country], dict) else {"data": data[country]}
                elif isinstance(data, dict):
                    out["seasonality"] = data
                else:
                    out["seasonality"] = {"data": data}
                _set_cache(key, out["seasonality"])
                out["sources_used"].append("seasonality")
            except Exception:
                out["seasonality"] = {"error": "fetch_failed"}

    # REST Countries (free, no key) — metadata for geo
    cc_key = f"restcountries:{country}"
    cc_cached = _get_cached(cc_key)
    if cc_cached is not None:
        out["country_info"] = cc_cached
        if "restcountries" not in out["sources_used"]:
            out["sources_used"].append("restcountries")
    else:
        cc = await fetch_rest_countries(country)
        if cc.get("ok"):
            out["country_info"] = {k: v for k, v in cc.items() if k != "ok"}
            _set_cache(cc_key, out["country_info"])
            out["sources_used"].append("restcountries")

    return out
