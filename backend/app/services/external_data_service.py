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


async def get_external_signals(
    country_code: str,
    days: int = 7,
    news_api_key: Optional[str] = None,
    seasonality_data_url: Optional[str] = None,
) -> dict[str, Any]:
    """
    Aggregate external signals for a country and period.
    Returns normalized structure for use in profitability/recommendations.
    """
    country = (country_code or "us").lower()[:2]
    out: dict[str, Any] = {
        "country": country,
        "period_days": days,
        "sources_used": [],
        "news": None,
        "seasonality": None,
    }

    # News (NewsAPI)
    if news_api_key and (news_api_key or "").strip():
        key = _cache_key("news", country, days)
        cached = _get_cached(key)
        if cached is not None:
            out["news"] = cached
            out["sources_used"].append("newsapi")
        else:
            news_payload = await fetch_news_api(country, news_api_key.strip())
            if news_payload.get("ok"):
                out["news"] = {"headlines": news_payload.get("headlines", []), "count": len(news_payload.get("headlines", []))}
                _set_cache(key, out["news"])
                out["sources_used"].append("newsapi")
            else:
                out["news"] = {"headlines": [], "error": news_payload.get("error")}

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

    return out
